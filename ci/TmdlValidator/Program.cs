// Validates a Power BI semantic model stored as TMDL, without needing Power BI Desktop.
//
//   dotnet run --project ci/TmdlValidator -- <path-to-definition-folder> [--bim <out.bim>]
//
// 1. Deserializes the folder with the Tabular Object Model (TOM). This catches TMDL syntax errors,
//    unknown properties and broken object references (sort-by columns, hierarchy levels, relationship
//    columns, roles).
// 2. Checks relationship column data types match on both ends.
// 3. Checks every DAX reference ('Table'[Column], [Measure]) in measures, calculation items, format
//    string expressions, calculated tables and RLS filters resolves to a real object. TOM does not parse
//    DAX offline, so a renamed column or measure would otherwise only fail after deployment.
// Exits 1 on any error. Errors use GitHub Actions annotation syntax when running in Actions.

using System.Text.RegularExpressions;
using Microsoft.AnalysisServices.Tabular;
using TomTable = Microsoft.AnalysisServices.Tabular.Table;

if (args.Length < 1)
{
    Console.Error.WriteLine("usage: TmdlValidator <definition-folder> [--bim <out.bim>]");
    return 2;
}

var folder = Path.GetFullPath(args[0]);
string? bimPath = null;
for (var i = 1; i < args.Length - 1; i++)
    if (args[i] == "--bim") bimPath = args[i + 1];

var inActions = Environment.GetEnvironmentVariable("GITHUB_ACTIONS") == "true";
var errors = 0;
void Error(string message, string? file = null, int? line = null)
{
    errors++;
    if (inActions)
        Console.WriteLine(file is null ? $"::error::{message}" : $"::error file={file},line={line ?? 1}::{message}");
    else
        Console.WriteLine($"ERROR {(file is null ? "" : $"{file}:{line} ")}{message}");
}

Database db;
try
{
    db = TmdlSerializer.DeserializeDatabaseFromFolder(folder);
}
catch (Exception ex)
{
    // TMDL parse/reference exceptions expose the offending document and line; read them by
    // reflection so this keeps working across TOM versions that move the exception types.
    var document = ex.GetType().GetProperty("Document")?.GetValue(ex) as string;
    var line = ex.GetType().GetProperty("Line")?.GetValue(ex) as int?;
    Error($"{ex.GetType().Name}: {ex.Message}", document, line);
    return 1;
}

var model = db.Model;
Console.WriteLine($"Loaded model: {model.Tables.Count} tables, {model.Tables.Sum(t => t.Measures.Count)} measures, " +
                  $"{model.Relationships.Count} relationships, {model.Roles.Count} roles (compatibility level {db.CompatibilityLevel}).");

// --- relationship data types -------------------------------------------------------------------
foreach (var rel in model.Relationships.OfType<SingleColumnRelationship>())
{
    if (rel.FromColumn.DataType != rel.ToColumn.DataType)
        Error($"Relationship '{rel.Name}': {Describe(rel.FromColumn)} is {rel.FromColumn.DataType} but {Describe(rel.ToColumn)} is {rel.ToColumn.DataType}.");
}

// --- DAX references ----------------------------------------------------------------------------
var measureNames = model.Tables.SelectMany(t => t.Measures).Select(m => m.Name).ToHashSet(StringComparer.OrdinalIgnoreCase);
var qualifiedRef = new Regex(@"(?:'((?:[^']|'')+)'|\b([A-Za-z_][A-Za-z0-9_]*))\s*\[([^\]]+)\]", RegexOptions.Compiled);
var bareRef = new Regex(@"\[([^\]]+)\]", RegexOptions.Compiled);
var DaxKeywords = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
{
    "RETURN", "VAR", "IN", "NOT", "AND", "OR", "THEN", "ELSE", "DEFINE", "EVALUATE", "MEASURE", "ORDER", "BY", "ASC", "DESC",
};

void CheckDax(string? dax, string owner, TomTable? rowContextTable)
{
    if (string.IsNullOrWhiteSpace(dax)) return;
    var code = StripCommentsAndStrings(dax);

    // An unquoted keyword in front of a bracket ("RETURN [Sales]") is not a table reference.
    var withoutQualified = qualifiedRef.Replace(code, m =>
    {
        if (!m.Groups[1].Success && DaxKeywords.Contains(m.Groups[2].Value))
            return m.Value;
        var tableName = m.Groups[1].Success ? m.Groups[1].Value.Replace("''", "'") : m.Groups[2].Value;
        var objectName = m.Groups[3].Value.Replace("]]", "]");
        var table = model.Tables.Find(tableName);
        if (table is null)
            Error($"{owner}: unknown table '{tableName}' in reference {m.Value}");
        else if (table.Columns.Find(objectName) is null && table.Measures.Find(objectName) is null)
            Error($"{owner}: '{tableName}' has no column or measure [{objectName}]");
        return " ";
    });

    foreach (Match m in bareRef.Matches(withoutQualified))
    {
        var name = m.Groups[1].Value;
        if (measureNames.Contains(name)) continue;
        if (rowContextTable?.Columns.Find(name) is not null) continue;
        Error($"{owner}: [{name}] is not a measure{(rowContextTable is null ? "" : $" or a column of '{rowContextTable.Name}'")}");
    }
}

foreach (var table in model.Tables)
{
    foreach (var measure in table.Measures)
    {
        CheckDax(measure.Expression, $"Measure [{measure.Name}]", null);
        CheckDax(measure.FormatStringDefinition?.Expression, $"Format string of [{measure.Name}]", null);
    }
    foreach (var column in table.Columns.OfType<CalculatedColumn>())
        CheckDax(column.Expression, $"Calculated column '{table.Name}'[{column.Name}]", table);
    foreach (var partition in table.Partitions)
        if (partition.Source is CalculatedPartitionSource calc)
            CheckDax(calc.Expression, $"Calculated table '{table.Name}'", null);
    if (table.CalculationGroup is not null)
        foreach (var item in table.CalculationGroup.CalculationItems)
        {
            CheckDax(item.Expression, $"Calculation item '{table.Name}'[{item.Name}]", null);
            CheckDax(item.FormatStringDefinition?.Expression, $"Format string of calculation item [{item.Name}]", null);
        }
}
foreach (var role in model.Roles)
    foreach (var permission in role.TablePermissions)
        CheckDax(permission.FilterExpression, $"Role '{role.Name}' filter on '{permission.Table.Name}'", permission.Table);

// --- output ---------------------------------------------------------------------------------------
if (bimPath is not null)
{
    // PBIP's database.tmdl is nameless, but .bim consumers such as Tabular Editor require a name.
    // Use the item folder name ("ContosoRetail.SemanticModel" -> "ContosoRetail").
    if (string.IsNullOrEmpty(db.Name))
    {
        var itemFolder = Path.GetFileName(Path.GetDirectoryName(folder.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)))!;
        db.Name = db.ID = itemFolder.Replace(".SemanticModel", "");
    }
    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(bimPath))!);
    File.WriteAllText(bimPath, JsonSerializer.SerializeDatabase(db, new SerializeOptions { IgnoreInferredObjects = true, IgnoreInferredProperties = true, IgnoreTimestamps = true }));
    Console.WriteLine($"Wrote {bimPath}");
}

Console.WriteLine(errors == 0 ? "TMDL validation passed." : $"TMDL validation failed with {errors} error(s).");
return errors == 0 ? 0 : 1;

static string Describe(Column c) => $"'{c.Table.Name}'[{c.Name}]";

// Removes // and -- line comments, /* */ block comments and "string literals" (DAX escapes quotes by
// doubling them) so brackets inside text are not mistaken for references.
static string StripCommentsAndStrings(string dax)
{
    var sb = new System.Text.StringBuilder(dax.Length);
    for (var i = 0; i < dax.Length; i++)
    {
        var c = dax[i];
        var next = i + 1 < dax.Length ? dax[i + 1] : '\0';
        if (c == '"')
        {
            i++;
            while (i < dax.Length)
            {
                if (dax[i] == '"' && i + 1 < dax.Length && dax[i + 1] == '"') { i += 2; continue; }
                if (dax[i] == '"') break;
                i++;
            }
            sb.Append("\"\"");
        }
        else if ((c == '/' && next == '/') || (c == '-' && next == '-'))
        {
            while (i < dax.Length && dax[i] != '\n') i++;
            sb.Append('\n');
        }
        else if (c == '/' && next == '*')
        {
            i += 2;
            while (i + 1 < dax.Length && !(dax[i] == '*' && dax[i + 1] == '/')) i++;
            i++;
            sb.Append(' ');
        }
        else if (c == '\'')
        {
            // Quoted table name: copy verbatim (it can contain characters like '-' or '/').
            sb.Append(c);
            i++;
            while (i < dax.Length)
            {
                if (dax[i] == '\'' && i + 1 < dax.Length && dax[i + 1] == '\'') { sb.Append("''"); i += 2; continue; }
                sb.Append(dax[i]);
                if (dax[i] == '\'') break;
                i++;
            }
        }
        else
        {
            sb.Append(c);
        }
    }
    return sb.ToString();
}
