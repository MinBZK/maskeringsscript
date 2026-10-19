"""Verify a recorded run against current inputs and write unsigned provenance.

This verifies consistency, not independent execution or human approval.
"""
import argparse
import hashlib
import json
from pathlib import Path

from coverage_eval import METRIC
from harness_config import repo_root
from measurement import file_sha, utc_now, verify_measurement
from scorecard import _validate_card, _reject_nonfinite_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--note', required=True, help='Maintainer assessment; not verified by this tool')
    parser.add_argument('--backbone-config', type=Path, help='Optional extra check against the recorded backbone hash')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    if args.output.exists() and not args.replace:
        parser.error('Provenance already exists; review it before using --replace.')
    if args.output.resolve() == args.card.resolve():
        parser.error('Output must not overwrite the scorecard.')
    try:
        raw = args.card.read_bytes()
        card = json.loads(raw.decode('utf-8'), parse_constant=_reject_nonfinite_json)
        _validate_card(card, 'Scorecard')
        receipt = verify_measurement(card, repo_root())
        inputs = receipt['inputs']
        if args.backbone_config and file_sha(args.backbone_config) != inputs['sha256'].get('model/backbone_config'):
            raise ValueError('The supplied backbone config differs from the measured backbone.')
        if args.card.read_bytes() != raw:
            raise ValueError('The scorecard file changed during verification.')
        result = {'provenance_schema': 2, 'metric': METRIC, 'generated_utc': utc_now(),
                  'measurement_started_utc': receipt['started_utc'],
                  'measurement_finished_utc': receipt['finished_utc'],
                  'measurement_result_sha256': receipt['result_sha256'],
                  'git_sha_full': inputs['git_sha_full'],
                  'python': inputs['environment']['python'], 'platform': inputs['environment']['platform'],
                  'environment': inputs['environment'], 'note': args.note,
                  'scope': 'Unsigned consistency record of a run receipt and matching current inputs; not independent proof of execution or human review.',
                  'sha256': {**inputs['sha256'], 'scorecard': hashlib.sha256(raw).hexdigest()}}
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print('Verified run provenance written:', args.output.name)


if __name__ == '__main__':
    main()
