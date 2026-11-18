"""Exact record exclusions for exported CSVs; immutable run snapshot stays intact."""
from approve_tool import digest, encoded


def record_key(row, fields):
    return digest(encoded([[k, row[k]] for k in fields if k != 'approve']))


def filtered_export(exporter, exclusion):
    excluded = set(exclusion['record_keys'])
    identity_fields = exclusion['fields']
    def export(path, rows, fields, results, encoding, newline):
        if path.name not in ('reviewed.csv', 'selected_rows.csv'):
            return exporter(path, rows, fields, results, encoding, newline)
        kept = []
        mapped = {}
        for i, row in enumerate(rows):
            if record_key(row, identity_fields) in excluded:
                continue
            if i in results:
                mapped[len(kept)] = results[i]
            kept.append(row)
        return exporter(path, kept, fields, mapped, encoding, newline)
    return export
