#!/usr/bin/env python
from __future__ import with_statement
import os
import re
import sys
import glob
import datetime

try:
    import json
except:
    import simplejson as json

from fiftystates import settings
from fiftystates.backend import db
from fiftystates.backend.utils import (base_arg_parser, prepare_obj, update,
                                       insert_with_id)

import argparse
import name_tools


def import_committees(state, data_dir):
    data_dir = os.path.join(data_dir, state)
    pattern = os.path.join(data_dir, 'committees', '*.json')

    meta = db.metadata.find_one({'_id': state})
    current_term = meta['terms'][-1]['name']

    paths = glob.glob(pattern)

    if not paths:
        # Not standalone committees
        for legislator in db.legislators.find({
            'roles': {'$elemMatch': {'term': current_term}}}):

            for role in legislator['roles']:
                if (role['type'] == 'committee member' and
                    'committee_id' not in role):

                    spec = {'state': role['state'],
                            'chamber': role['chamber'],
                            'committee': role['committee']}
                    if 'subcommittee' in role:
                        spec['subcommittee'] = role['subcommittee']

                    committee = db.committees.find_one(spec)

                    if not committee:
                        committee = spec
                        committee['_type'] = 'committee'
                        committee['members'] = []
                        insert_with_id(committee)

                    for member in committee['members']:
                        if member['leg_id'] == legislator['leg_id']:
                            break
                    else:
                        committee['members'].append(
                            {'name': legislator['full_name'],
                             'leg_id': legislator['leg_id'],
                             'role': 'member'})
                        db.committees.save(committee, safe=True)

                        role['committee_id'] = committee['_id']

            db.legislators.save(legislator, safe=True)

    for path in paths:
        with open(path) as f:
            data = prepare_obj(json.load(f))

        spec = {'state': state,
                'committee': data['committee']}
        if 'subcommittee' in data:
            spec['subcommittee'] = data['subcommittee']

        committee = db.committees.find_one(spec)

        if not committee:
            insert_with_id(data)
            committee = data
        else:
            update(committee, data, db.committees)

        for member in committee['members']:
            if not member['legislator']:
                continue

            (pre, first, last, suff) = name_tools.split(member['legislator'])

            found = db.legislators.find({
                    'first_name': first,
                    'last_name': last,
                    'roles': {'$elemMatch': {'term': current_term,
                                             'state': state}}})

            if found.count() > 1:
                print "Too many matches for %s" % member['legislator'].encode(
                    'ascii', 'ignore')
                continue
            elif found.count() == 0:
                print "No matches for %s" % member['legislator'].encode(
                    'ascii', 'ignore')
                continue

            legislator = found[0]

            member['leg_id'] = legislator['_id']

            for role in legislator['roles']:
                if (role['type'] == 'committee member' and
                    role['term'] == current_term and
                    role['committee_id'] == committee['_id']):
                    break
            else:
                new_role = {'type': 'committee member',
                            'committee': committee['committee'],
                            'term': current_term,
                            'chamber': committee['chamber'],
                            'committee_id': committee['_id'],
                            'state': state}
                if 'subcommittee' in committee:
                    new_role['subcommittee'] = committee['subcommittee']
                legislator['roles'].append(new_role)
                legislator['updated_at'] = datetime.datetime.now()
                db.legislators.save(legislator, safe=True)

        db.committees.save(committee, safe=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        parents=[base_arg_parser],
        description=('Import scraped (separate file) comittees into a '
                     'mongo database.'))

    parser.add_argument('--data_dir', '-d', type=str,
                        help='the base Fifty State data directory')

    args = parser.parse_args()

    if args.data_dir:
        data_dir = args.data_dir
    else:
        data_dir = settings.FIFTYSTATES_DATA_DIR

    import_committees(args.state, data_dir)
