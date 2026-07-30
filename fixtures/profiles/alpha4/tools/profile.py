#!/usr/bin/env python3
import argparse, json
p = argparse.ArgumentParser(); p.add_argument('--json', action='store_true'); p.add_argument('command'); args, unknown = p.parse_known_args()
print(json.dumps({'schema': 'fixture.profile-result.v1', 'profileId': 'alpha4-fixture', 'command': args.command, 'unknown': unknown, 'selectedSkills': ['alpha4-router'], 'plannedGates': [], 'structureProjection': {'schema': 'fixture.alpha4-structure-projection.v1', 'kind': 'fixture'}}))
