// PerfKit: measure the model running in Power BI Desktop through its local Analysis Services instance.
// The port is in %USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces\*\Data\msmdsrv.port.txt.
//
//   PerfKit trace    <port> <trace.jsonl> <stopfile>  record every query (and refresh) until <stopfile> exists;
//                                                     click through the report meanwhile
//   PerfKit replay   <port> <trace.jsonl>             rerun each distinct DAX query cold (cache cleared), then warm
//   PerfKit vertipaq <port>                           model size by table and column (storage DMVs)
//   PerfKit syncmeasures <port> <tmdl folder>         copy measure expressions from TMDL into the running model
//   PerfKit refresh  <port>                           full refresh of the running model, timed; like Desktop's
//                                                     Refresh, it ignores the Sales incremental refresh policy
using System.Diagnostics;
using System.Text.Json;
using Microsoft.AnalysisServices.AdomdClient;
using Tab = Microsoft.AnalysisServices.Tabular;
using Amo = Microsoft.AnalysisServices;

var cmd = args[0];
var port = args[1];
var cs = $"Data Source=localhost:{port}";

if (cmd == "trace")
{
    var outFile = args[2]; var stopFile = args[3];
    var server = new Tab.Server();
    server.Connect(cs);
    var trace = server.Traces.Add("perfkit_" + Guid.NewGuid().ToString("N")[..8]);
    foreach (var ec in new[] { Amo.TraceEventClass.QueryEnd, Amo.TraceEventClass.CommandEnd })
    {
        var ev = trace.Events.Add(ec);
        foreach (var col in new[] { Amo.TraceColumn.TextData, Amo.TraceColumn.Duration, Amo.TraceColumn.CpuTime,
                                    Amo.TraceColumn.EventSubclass, Amo.TraceColumn.StartTime, Amo.TraceColumn.EventClass })
            ev.Columns.Add(col);
    }
    using var writer = new StreamWriter(outFile, append: false) { AutoFlush = true };
    var gate = new object();
    trace.OnEvent += (s, e) =>
    {
        var rec = new Dictionary<string, object>
        {
            ["event"] = e.EventClass.ToString(),
            ["subclass"] = e.EventSubclass.ToString(),
            ["start"] = e.StartTime.ToString("o"),
            ["durationMs"] = e.Duration,
            ["cpuMs"] = e.CpuTime,
            ["text"] = e.TextData,
        };
        lock (gate) writer.WriteLine(JsonSerializer.Serialize(rec));
    };
    trace.Update();
    trace.Start();
    Console.WriteLine($"tracing on port {port}; create {stopFile} to stop");
    while (!File.Exists(stopFile)) Thread.Sleep(1000);
    trace.Stop();
    trace.Drop();
    server.Disconnect();
    Console.WriteLine("stopped");
}
else if (cmd == "syncmeasures")
{
    // Copy measure expressions from a TMDL folder into the running model (like Tabular Editor's save to Desktop).
    var source = Tab.TmdlSerializer.DeserializeDatabaseFromFolder(args[2]);
    var server = new Tab.Server();
    server.Connect(cs);
    var model = server.Databases[0].Model;
    foreach (var table in source.Model.Tables)
        foreach (var m in table.Measures)
        {
            var live = model.Tables.Find(table.Name)?.Measures.Find(m.Name);
            if (live != null && live.Expression != m.Expression)
            {
                live.Expression = m.Expression;
                Console.WriteLine($"updated {table.Name}[{m.Name}]");
            }
        }
    model.SaveChanges();
    server.Disconnect();
}
else if (cmd == "refresh")
{
    var server = new Tab.Server();
    server.Connect(cs);
    var model = server.Databases[0].Model;
    var sw = Stopwatch.StartNew();
    // Applying the policy would split Sales into yearly partitions, and Desktop would save those into
    // Sales.tmdl on the next Ctrl+S. Desktop's own Refresh keeps the single RangeStart/RangeEnd partition.
    model.RequestRefresh(Tab.RefreshType.Full, Tab.RefreshPolicyBehavior.Ignore);
    model.SaveChanges();
    Console.WriteLine($"full refresh took {sw.Elapsed.TotalSeconds:N0} s");
    server.Disconnect();
}
else if (cmd == "replay")
{
    // Accepts a trace file (only its DAX queries are used) or lines of {"label", "text"}.
    var queries = new List<(string Label, string Text)>();
    var seen = new HashSet<string>();
    foreach (var line in File.ReadAllLines(args[2]))
    {
        var doc = JsonDocument.Parse(line).RootElement;
        if (doc.TryGetProperty("event", out var ev) && ev.GetString() != "QueryEnd") continue;
        var text = doc.GetProperty("text").GetString();
        if (string.IsNullOrWhiteSpace(text) || !seen.Add(string.Join(' ', text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries)))) continue;
        queries.Add((doc.TryGetProperty("label", out var l) ? l.GetString() : $"query {queries.Count + 1}", text));
    }
    using var conn = new AdomdConnection(cs);
    conn.Open();
    var dbId = conn.Database;
    var colds = new List<long>(); var warms = new List<long>();
    foreach (var (label, query) in queries)
    {
        ClearCache(conn, dbId);
        var cold = Run(conn, query, out var rows, out var err);
        var warm = Run(conn, query, out _, out _);
        colds.Add(cold); warms.Add(warm);
        Console.WriteLine(JsonSerializer.Serialize(new { label, coldMs = cold, warmMs = warm, rows, error = err }));
    }
    colds.Sort(); warms.Sort();
    if (colds.Count > 0)
        Console.Error.WriteLine($"{colds.Count} queries | cold: median {colds[colds.Count / 2]} ms, p90 {colds[(int)(colds.Count * 0.9)]} ms, " +
                                $"max {colds[^1]} ms, over 1 s: {colds.Count(c => c > 1000)} | warm: median {warms[warms.Count / 2]} ms, max {warms[^1]} ms");
}
else if (cmd == "vertipaq")
{
    using var conn = new AdomdConnection(cs);
    conn.Open();
    var sizes = new Dictionary<(string, string), long>();
    var rowsByTable = new Dictionary<string, long>();
    using (var c = new AdomdCommand("SELECT DIMENSION_NAME, ATTRIBUTE_NAME, COLUMN_TYPE, DICTIONARY_SIZE FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS", conn))
    using (var r = c.ExecuteReader())
        while (r.Read())
            if (Convert.ToString(r.GetValue(2)) == "BASIC_DATA")
                Add(sizes, (Convert.ToString(r.GetValue(0)), Convert.ToString(r.GetValue(1))), Convert.ToInt64(r.GetValue(3)));
    using (var c = new AdomdCommand("SELECT DIMENSION_NAME, TABLE_ID, COLUMN_ID, USED_SIZE, RECORDS_COUNT, SEGMENT_NUMBER FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS", conn))
    using (var r = c.ExecuteReader())
        while (r.Read())
        {
            var table = Convert.ToString(r.GetValue(0));
            var tableId = Convert.ToString(r.GetValue(1));
            var columnId = Convert.ToString(r.GetValue(2));
            // Data segments live in "<Table> (id)"; hierarchies (H$) and relationships (R$) are extra structures.
            var column = tableId.StartsWith("H$") ? "(hierarchies)" : tableId.StartsWith("R$") ? "(relationships)" : columnId;
            Add(sizes, (table, column), Convert.ToInt64(r.GetValue(3)));
        }
    foreach (var g in sizes.GroupBy(k => k.Key.Item1).OrderByDescending(g => g.Sum(x => x.Value)))
    {
        Console.WriteLine($"{g.Key,-28} {g.Sum(x => x.Value) / 1048576.0,10:N1} MB");
        foreach (var c in g.OrderByDescending(x => x.Value).Take(6))
            Console.WriteLine($"    {c.Key.Item2,-40} {c.Value / 1048576.0,10:N2} MB");
    }
    Console.WriteLine($"TOTAL {sizes.Values.Sum() / 1048576.0:N1} MB");
}

static void Add<TK>(Dictionary<TK, long> d, TK k, long v) where TK : notnull => d[k] = d.GetValueOrDefault(k) + v;

static void ClearCache(AdomdConnection conn, string db)
{
    var xmla = $"<ClearCache xmlns=\"http://schemas.microsoft.com/analysisservices/2003/engine\"><Object><DatabaseID>{db}</DatabaseID></Object></ClearCache>";
    using var c = new AdomdCommand(xmla, conn);
    c.ExecuteNonQuery();
}

static long Run(AdomdConnection conn, string query, out int rows, out string error)
{
    rows = 0; error = null;
    var sw = Stopwatch.StartNew();
    try
    {
        using var c = new AdomdCommand(query, conn);
        using var r = c.ExecuteReader();
        while (r.Read()) rows++;
    }
    catch (Exception ex) { error = ex.Message.Split('\n')[0]; }
    return sw.ElapsedMilliseconds;
}
