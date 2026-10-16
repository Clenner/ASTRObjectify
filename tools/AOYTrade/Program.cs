// AOYTrade: minuscule UAssetAPI helper for ASTRObjectify.
// Loads a cooked .uasset through UAssetAPI instead of raw-byte parsing.
// Commands:
//   verify <file.uasset>                                     load + VerifyBinaryEquality, print JSON summary
//   dump <file.uasset>                                       print table rows as JSON
//   set-value <f> <sec> <item> <v>                           set one trade value
//   set-values <f> [<sec> <item> <v>]...                     set many (single load+save)
//   add-row <f> <sec> <item> <v>                             append a trade row
//   remove-row <f> <sec> <item>                              delete a trade row
// Refs are import indices as integers (e.g. -43); values are floats.
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.PropertyTypes.Objects;
using UAssetAPI.PropertyTypes.Structs;
using UAssetAPI.UnrealTypes;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: AOYTrade <verify|dump> <file.uasset>");
    return 2;
}

string command = args[0];
string path = Path.GetFullPath(args[1]);
if (!File.Exists(path))
{
    Console.Error.WriteLine($"Not found: {path}");
    return 1;
}

UAsset asset;
try
{
    asset = new UAsset(path, EngineVersion.VER_UE4_27);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Load failed: {ex.GetType().Name}: {ex.Message}");
    return 1;
}

if (command == "verify")
{
    bool ok;
    try
    {
        ok = asset.VerifyBinaryEquality();
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Verify failed: {ex.GetType().Name}: {ex.Message}");
        return 1;
    }
    var exports = asset.Exports.Select((e, i) => new
    {
        index = i + 1,
        name = e.ObjectName.ToString(),
        kind = e.GetType().Name,
    }).ToList();
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
    {
        file = path,
        binary_equal = ok,
        export_count = exports.Count,
        exports,
    }));
    return ok ? 0 : 3;
}

if (command == "dump")
{
    var rows = new List<object>();
    foreach (var exp in asset.Exports)
    {
        if (exp is DataTableExport dt && dt.Table?.Data != null)
        {
            int ri = 0;
            foreach (var row in dt.Table.Data)
            {
                var fields = new Dictionary<string, string>();
                foreach (var prop in row.Value)
                    fields[prop.Name.ToString()] = FlatProp(prop);
                rows.Add(new { table = exp.ObjectName.ToString(), row = row.Name.ToString(), index = ri++, fields });
            }
        }
        if (exp is NormalExport ne && ne.Data != null)
        {
            foreach (var prop in ne.Data)
                rows.Add(new { table = exp.ObjectName.ToString(), prop = DumpProp(prop, 0) });
        }
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file = path, rows }));
    return 0;
}

if (command == "sections")
{
    var tradeMap = FindTradeMap(asset);
    if (tradeMap == null)
    {
        Console.Error.WriteLine("No trade map found in this asset.");
        return 4;
    }
    var sections = new List<object>();
    foreach (var kv in tradeMap.Value)
    {
        if (kv.Key is not ObjectPropertyData skey)
            continue;
        var rows = new List<object>();
        var inner = InnerRows(kv.Value);
        if (inner != null)
        {
            foreach (var row in inner.Value)
            {
                if (row.Key is ObjectPropertyData rok && row.Value is FloatPropertyData f)
                {
                    rows.Add(new
                    {
                        item_ref = rok.Value.Index,
                        item_name = ImportName(asset, rok.Value.Index),
                        value = f.Value,
                    });
                }
            }
        }
        sections.Add(new
        {
            key_ref = skey.Value.Index,
            key_name = ImportName(asset, skey.Value.Index),
            rows,
        });
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file = path, sections }));
    return 0;
}

if (command == "resolve")
{
    if (args.Length < 3)
    {
        Console.Error.WriteLine($"Usage: AOYTrade resolve <file.uasset> <name>");
        return 2;
    }
    string want = args[2];
    for (int pass = 0; pass < 3; pass++)
    {
        for (int i = 0; i < asset.Imports.Count; i++)
        {
            string have = asset.Imports[i].ObjectName.ToString();
            bool match = pass switch
            {
                0 => have == want,
                1 => have.EndsWith("_C") && have[..^2] == want,
                _ => string.Equals(have.EndsWith("_C") ? have[..^2] : have, want, StringComparison.OrdinalIgnoreCase),
            };
            if (match)
            {
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
                {
                    file = path,
                    name = want,
                    item_ref = -i - 1,
                }));
                return 0;
            }
        }
    }
    Console.Error.WriteLine($"Item is not referenced by this file: {want}");
    return 4;
}

if (command == "add-section")
{
    if (args.Length < 3 || !int.TryParse(args[2], out int keyRef))
    {
        Console.Error.WriteLine($"Usage: AOYTrade add-section <file.uasset> <key_ref>");
        return 2;
    }
    var tradeMap = FindTradeMap(asset);
    if (tradeMap == null)
    {
        Console.Error.WriteLine("No trade map found in this asset.");
        return 4;
    }
    foreach (var kv in tradeMap.Value)
    {
        if (kv.Key is ObjectPropertyData ok && ok.Value.Index == keyRef)
        {
            Console.Error.WriteLine("That section already exists.");
            return 4;
        }
    }
    var last = tradeMap.Value.Last();
    var newKey = (ObjectPropertyData)last.Key.Clone();
    newKey.Value = new FPackageIndex(keyRef);
    if (last.Value is not StructPropertyData template)
    {
        Console.Error.WriteLine("Unexpected section layout, refusing to modify.");
        return 4;
    }
    var newStruct = (StructPropertyData)template.Clone();
    bool cleared = false;
    foreach (var prop in newStruct.Value)
    {
        if (prop is MapPropertyData m)
        {
            m.Value.Clear();
            cleared = true;
        }
    }
    if (!cleared)
    {
        Console.Error.WriteLine("Unexpected section layout, refusing to modify.");
        return 4;
    }
    tradeMap.Value.Add(newKey, newStruct);
    try
    {
        asset.Write(path);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Save failed: {ex.GetType().Name}: {ex.Message}");
        return 1;
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file = path, command, key_ref = keyRef }));
    return 0;
}

if (command == "remove-section")
{
    if (args.Length < 3 || !int.TryParse(args[2], out int keyRef))
    {
        Console.Error.WriteLine($"Usage: AOYTrade remove-section <file.uasset> <key_ref>");
        return 2;
    }
    var tradeMap = FindTradeMap(asset);
    if (tradeMap == null)
    {
        Console.Error.WriteLine("No trade map found in this asset.");
        return 4;
    }
    if (tradeMap.Value.Count <= 1)
    {
        Console.Error.WriteLine("Cannot remove the last remaining section.");
        return 4;
    }
    PropertyData? victim = null;
    foreach (var kv in tradeMap.Value)
    {
        if (kv.Key is ObjectPropertyData ok && ok.Value.Index == keyRef)
        {
            victim = kv.Key;
            break;
        }
    }
    if (victim == null)
    {
        Console.Error.WriteLine($"No such trade section: {keyRef}");
        return 4;
    }
    tradeMap.Value.Remove(victim);
    try
    {
        asset.Write(path);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Save failed: {ex.GetType().Name}: {ex.Message}");
        return 1;
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file = path, command, key_ref = keyRef }));
    return 0;
}

if (command is "add-row" or "remove-row")
{
    if (args.Length < 4)
    {
        Console.Error.WriteLine($"Usage: AOYTrade {command} <file.uasset> <section_ref> <item_ref> [value]");
        return 2;
    }
    if (!int.TryParse(args[2], out int sectionRef) || !int.TryParse(args[3], out int itemRef))
    {
        Console.Error.WriteLine("section_ref and item_ref must be integers (e.g. -43, -34).");
        return 2;
    }
    float value = 0;
    if (command == "add-row")
    {
        if (args.Length < 5 || !float.TryParse(args[4], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out value))
        {
            Console.Error.WriteLine($"Usage: AOYTrade add-row <file.uasset> <section_ref> <item_ref> <value>");
            return 2;
        }
        if (value is < 0 or > 1000000)
        {
            Console.Error.WriteLine($"Bad trade value: {args[4]}");
            return 4;
        }
    }

    var tradeMap = FindTradeMap(asset);
    if (tradeMap == null)
    {
        Console.Error.WriteLine("No trade map found in this asset.");
        return 4;
    }
    PropertyData? sectionKey = null;
    MapPropertyData? inner = null;
    foreach (var kv in tradeMap.Value)
    {
        if (kv.Key is ObjectPropertyData ok && ok.Value.Index == sectionRef)
        {
            sectionKey = kv.Key;
            inner = InnerRows(kv.Value);
            break;
        }
    }
    if (sectionKey == null || inner == null)
    {
        Console.Error.WriteLine($"No such trade section: {sectionRef}");
        return 4;
    }

    if (command == "add-row")
    {
        foreach (var kv in inner.Value)
        {
            if (kv.Key is ObjectPropertyData ok && ok.Value.Index == itemRef)
            {
                Console.Error.WriteLine($"Item {itemRef} is already in section {sectionRef}.");
                return 4;
            }
        }
        var template = FirstRowTemplate(tradeMap);
        if (template.row == null)
        {
            Console.Error.WriteLine(template.error ?? "No existing trade row to use as a template.");
            return 4;
        }
        var templateKey = (ObjectPropertyData)template.row.Value.Key.Clone();
        templateKey.Value = new FPackageIndex(itemRef);
        var templateVal = (FloatPropertyData)template.row.Value.Value.Clone();
        templateVal.Value = value;
        inner.Value.Add(templateKey, templateVal);
    }
    else // remove-row
    {
        PropertyData? victim = null;
        foreach (var kv in inner.Value)
        {
            if (kv.Key is ObjectPropertyData ok && ok.Value.Index == itemRef)
            {
                victim = kv.Key;
                break;
            }
        }
        if (victim == null)
        {
            Console.Error.WriteLine($"Item {itemRef} is not in section {sectionRef}.");
            return 4;
        }
        inner.Value.Remove(victim);
    }

    try
    {
        asset.Write(path);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Save failed: {ex.GetType().Name}: {ex.Message}");
        return 1;
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
    {
        file = path,
        command,
        section_ref = sectionRef,
        item_ref = itemRef,
        value,
    }));
    return 0;
}

if (command is "set-value" or "set-values")
{
    var triplets = new List<(int sec, int item, float val)>();
    if (command == "set-value")
    {
        if (args.Length < 5 || !int.TryParse(args[2], out int s) || !int.TryParse(args[3], out int i)
            || !float.TryParse(args[4], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float v))
        {
            Console.Error.WriteLine($"Usage: AOYTrade set-value <file.uasset> <section_ref> <item_ref> <value>");
            return 2;
        }
        triplets.Add((s, i, v));
    }
    else
    {
        if ((args.Length - 2) % 3 != 0 || args.Length < 5)
        {
            Console.Error.WriteLine($"Usage: AOYTrade set-values <file.uasset> [<section_ref> <item_ref> <value>]...");
            return 2;
        }
        for (int a = 2; a < args.Length; a += 3)
        {
            if (!int.TryParse(args[a], out int s) || !int.TryParse(args[a + 1], out int i)
                || !float.TryParse(args[a + 2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float v))
            {
                Console.Error.WriteLine($"Bad triplet starting at argument {a + 1}.");
                return 2;
            }
            triplets.Add((s, i, v));
        }
    }
    foreach (var (s, i, v) in triplets)
    {
        if (v is < 0 or > 1000000)
        {
            Console.Error.WriteLine($"Bad trade value: {v}");
            return 4;
        }
    }

    var tradeMap = FindTradeMap(asset);
    if (tradeMap == null)
    {
        Console.Error.WriteLine("No trade map found in this asset.");
        return 4;
    }
    foreach (var (s, i, v) in triplets)
    {
        bool found = false;
        foreach (var kv in tradeMap.Value)
        {
            if (kv.Key is not ObjectPropertyData ok || ok.Value.Index != s)
                continue;
            var inner = InnerRows(kv.Value);
            if (inner == null)
                continue;
            foreach (var row in inner.Value)
            {
                if (row.Key is ObjectPropertyData rok && rok.Value.Index == i && row.Value is FloatPropertyData f)
                {
                    f.Value = v;
                    found = true;
                    break;
                }
            }
            break;
        }
        if (!found)
        {
            Console.Error.WriteLine($"Item {i} is not in section {s}.");
            return 4;
        }
    }

    try
    {
        asset.Write(path);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Save failed: {ex.GetType().Name}: {ex.Message}");
        return 1;
    }
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
    {
        file = path,
        command,
        applied = triplets.Count,
    }));
    return 0;
}

string FlatProp(PropertyData prop) => prop switch
{
    FloatPropertyData f => f.Value.ToString(System.Globalization.CultureInfo.InvariantCulture),
    IntPropertyData i => i.Value.ToString(),
    NamePropertyData n => n.Value.ToString(),
    ObjectPropertyData o => o.Value.ToString(),
    _ => prop.GetType().Name,
};

object DumpProp(PropertyData prop, int depth)
{
    string typeName = prop.GetType().Name;
    string name = prop.Name.ToString();
    if (depth > 3) return new { name, type = typeName };
    return prop switch
    {
        MapPropertyData m => new
        {
            name,
            type = typeName,
            entries = m.Value.Select(kv => new
            {
                key = DumpProp(kv.Key, depth + 1),
                value = DumpProp(kv.Value, depth + 1),
            }).ToList(),
        },
        StructPropertyData s => new
        {
            name,
            type = typeName,
            fields = s.Value.Select(p => DumpProp(p, depth + 1)).ToList(),
        },
        ArrayPropertyData a => new
        {
            name,
            type = typeName,
            items = ((System.Collections.IEnumerable)a.Value).Cast<PropertyData>().Select(p => DumpProp(p, depth + 1)).ToList(),
        },
        _ => new { name, type = typeName, value = FlatProp(prop) },
    };
}

Console.Error.WriteLine($"Unknown command: {command}");
return 2;

MapPropertyData? FindTradeMap(UAsset asset)
{
    foreach (var exp in asset.Exports)
    {
        if (exp is NormalExport ne && ne.Data != null)
        {
            foreach (var prop in ne.Data)
            {
                if (prop is MapPropertyData m && m.Value.Count > 0)
                    return m;
            }
        }
    }
    return null;
}

MapPropertyData? InnerRows(PropertyData sectionValue)
{
    if (sectionValue is StructPropertyData s)
    {
        foreach (var prop in s.Value)
        {
            if (prop is MapPropertyData m)
                return m;
        }
    }
    return null;
}

string ImportName(UAsset asset, int importRef)
{
    int idx = -importRef - 1;
    if (0 <= idx && idx < asset.Imports.Count)
    {
        string name = asset.Imports[idx].ObjectName.ToString();
        if (name.EndsWith("_C"))
            name = name[..^2];
        return name;
    }
    return "";
}

(KeyValuePair<PropertyData, PropertyData>? row, string? error) FirstRowTemplate(MapPropertyData tradeMap)
{
    foreach (var kv in tradeMap.Value)
    {
        var inner = InnerRows(kv.Value);
        if (inner == null)
            continue;
        foreach (var row in inner.Value)
        {
            if (row.Key is ObjectPropertyData && row.Value is FloatPropertyData)
                return (row, null);
        }
    }
    return (null, "No existing trade row to use as a template.");
}
