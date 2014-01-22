# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import sqlalchemy as sa

from ceilometer.storage.sqlalchemy import models


def _paged(query, size):
    offset = 0
    while True:
        page = query.offset(offset).limit(size).execute()
        if page.rowcount <= 0:
            # There are no more rows
            break
        for row in page:
            yield row
        offset += size


def _convert_data_type(table, col, from_t, to_t, pk_attr='id'):
    temp_col_n = 'convert_data_type_temp_col'
    # Override column we're going to convert with from_t, since the type we're
    # replacing could be custom and we need to tell SQLALchemy how to perform
    # CRUD operations with it.
    table = sa.Table(table.name, table.metadata, sa.Column(col, from_t),
                     extend_existing=True)
    sa.Column(temp_col_n, to_t).create(table)

    key_attr = getattr(table.c, pk_attr)
    orig_col = getattr(table.c, col)
    new_col = getattr(table.c, temp_col_n)

    query = sa.select([key_attr, orig_col])
    for key, value in _paged(query, 1000):
        table.update().where(key_attr == key)\
            .values({temp_col_n: value}).execute()

    orig_col.drop()
    new_col.alter(name=col)


to_convert = [
    ('alarm', 'timestamp', 'id'),
    ('alarm', 'state_timestamp', 'id'),
    ('alarm_history', 'timestamp', 'alarm_id'),
]


def upgrade(migrate_engine):
    if migrate_engine.name == 'mysql':
        meta = sa.MetaData(bind=migrate_engine)
        for table_name, col_name, pk_attr in to_convert:
            table = sa.Table(table_name, meta, autoload=True)
            _convert_data_type(table, col_name, sa.DateTime(),
                               models.PreciseTimestamp(),
                               pk_attr=pk_attr)


def downgrade(migrate_engine):
    if migrate_engine.name == 'mysql':
        meta = sa.MetaData(bind=migrate_engine)
        for table_name, col_name, pk_attr in to_convert:
            table = sa.Table(table_name, meta, autoload=True)
            _convert_data_type(table, col_name, models.PreciseTimestamp(),
                               sa.DateTime(),
                               pk_attr=pk_attr)
