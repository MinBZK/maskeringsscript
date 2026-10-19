"""Conservative source-span coverage for placeholder substitution outputs.

An entity is fully redacted only if none of its alphanumeric source characters
can have survived in any valid alignment. Unsupported rewrites fail closed.
This measures annotated redaction coverage, not entity-detection precision.
"""
import re

METRIC = 'source-coverage-v2'
_NAME = r'[A-Za-z_][A-Za-z0-9_ ]*'
TAG_RE = re.compile(rf'<(?:{_NAME}|\({_NAME}\)|\[{_NAME}(?:,\s*C[0-9]+(?:\.[0-9]+)?)?\])>')

def _units(output):
    result = []
    pos = 0
    for match in TAG_RE.finditer(output):
        if match.start() > pos:
            result.append((False, output[pos:match.start()]))
        result.append((True, match.group()))
        pos = match.end()
    if pos < len(output):
        result.append((False, output[pos:]))
    return result

def _occurrences(text, literal):
    pos = text.find(literal)
    while pos >= 0:
        yield pos
        pos = text.find(literal, pos + 1)

def visible_source(text, output, max_cells=2_000_000):
    """Return possible visible positions, or None when alignment is unsupported.

    Literals match exactly and placeholders may consume any source span. Both
    directions are evaluated, so repeated source values cannot be assigned to
    whichever occurrence would make the result look safest.
    """
    if text == output:
        return set(range(len(text)))
    units = _units(output)
    n = len(text)
    if (n + 1) * (len(units) + 1) > max_cells:
        return None
    positions = [list(_occurrences(text, literal)) for _, literal in units]
    forward = [bytearray(n + 1) for _ in range(len(units) + 1)]
    forward[0][0] = 1
    for i, ((tag, literal), starts) in enumerate(zip(units, positions)):
        row, next_row = forward[i], forward[i + 1]
        if tag:
            first = row.find(b'\x01')
            if first >= 0:
                next_row[first:] = b'\x01' * (n + 1 - first)
        else:
            for start in starts:
                if row[start]:
                    next_row[start + len(literal)] = 1
    if not forward[-1][n]:
        return None
    backward = [bytearray(n + 1) for _ in range(len(units) + 1)]
    backward[-1][n] = 1
    for i in range(len(units) - 1, -1, -1):
        tag, literal = units[i]
        row, next_row = backward[i], backward[i + 1]
        if tag:
            last = next_row.rfind(b'\x01')
            if last >= 0:
                row[:last + 1] = b'\x01' * (last + 1)
        else:
            for start in positions[i]:
                if next_row[start + len(literal)]:
                    row[start] = 1
    # A tag also has a literal interpretation when it was already in the input.
    diff = [0] * (n + 1)
    for i, ((_, literal), starts) in enumerate(zip(units, positions)):
        for start in starts:
            end = start + len(literal)
            if forward[i][start] and backward[i + 1][end]:
                diff[start] += 1
                diff[end] -= 1
    visible = set()
    active = 0
    for i in range(n):
        active += diff[i]
        if active:
            visible.add(i)
    return visible

def gold_span(text, item):
    value = item['value']
    if 'start' in item or 'end' in item:
        start, end = item['start'], item['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != value:
            raise ValueError('Invalid gold offsets or value does not match the source span.')
        return start, end
    starts = list(_occurrences(text, value)) if value else []
    if len(starts) != 1:
        raise ValueError('Gold value is absent or repeated; provide explicit start/end offsets.')
    return starts[0], starts[0] + len(value)

def assess_record(record, output):
    text = record['text']
    visible = visible_source(text, output)
    assessed = []
    for item in record.get('pii', []):
        start, end = gold_span(text, item)
        significant = {i for i in range(start, end) if text[i].isalnum()}
        if not significant:
            raise ValueError('A gold span must contain identifying letters or digits.')
        retained = significant & visible if visible is not None else significant
        status = ('indeterminate' if visible is None else
                  'fully_masked' if not retained else
                  'unmasked' if retained == significant else 'partially_masked')
        assessed.append({**item, 'start': start, 'end': end, 'status': status,
                         'significant_chars': len(significant), 'visible_chars': len(retained)})
    return assessed
