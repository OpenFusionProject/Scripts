# %%
import json
import sys
from tqdm import tqdm
import mysql.connector

SPLIT_FIELDS = {
    "m_iMissionRewardItem": ("m_iMissionRewardItemID", "m_iMissionRewarItemType"),
    "m_iMissionRewardItem2": ("m_iMissionRewardItemID2", "m_iMissionRewardItemType2"),
    "m_iCSTItem": ("m_iCSTItemID", "m_iCSTItemNumNeeded"),
    "m_iCSUEnemy": ("m_iCSUEnemyID", "m_iCSUNumToKill"),
    "m_iCSUItem": ("m_iCSUItemID", "m_iCSUItemNumNeeded"),
    "m_iSTItem": ("m_iSTItemID", "m_iSTItemNumNeeded", "m_iSTItemDropRate"),
    "m_iSUItem_": ("m_iSUItem", "m_iSUInstancename"),
    "m_iFItem": ("m_iFItemID", "m_iFItemNumNeeded"),
}

# %%
def get_db_column_name(xdt_field_name):
    # special case 1
    if xdt_field_name == "m_iitemID":
        return "ItemID"
    
    try:
        # find the first uppercase character and split the string there
        idx_of_first_uppercase = next(i for i, c in enumerate(xdt_field_name) if c.isupper())
    except StopIteration:
        # special case 2
        if xdt_field_name == "m_ibattery":
            idx_of_first_uppercase = 3
        else:
            print(f"Could not find uppercase character in {xdt_field_name}")
            sys.exit(1)
    prefix = xdt_field_name[:idx_of_first_uppercase]
    db_field_name = xdt_field_name[idx_of_first_uppercase:]
    return db_field_name

# %%
def table_entry_to_tuple(table_entry):
    vals = []
    for field_name in table_entry:
        field = table_entry[field_name]
        vals.append(field)
    return tuple(vals)

def flatten_table_entry(table_entry):
    flattened_entry = {}
    for field_name in table_entry:
        field = table_entry[field_name]
        if type(field) == list:
            for i, item in enumerate(field):
                flattened_entry[f"{field_name}{i}"] = item
        else:
            flattened_entry[field_name] = field
    return flattened_entry

def handle_dict_table(table_entries, identifier_key, items_key):
    new_table_entries = []
    for table_entry in table_entries:
        identifier = table_entry[identifier_key]
        items = table_entry[items_key]
        for item in items:
            new_item = {}
            new_item[identifier_key] = identifier # needs to be first
            for field_name in item:
                new_item[field_name] = item[field_name]
            new_table_entries.append(new_item)
    return new_table_entries

def apply_schema(schema, entry):
    fixed_entry = {}
    padding = 0
    for field_name in schema:
        if field_name is None:
            fixed_entry[f"m_iPadding{padding}"] = 0
            padding += 1
            continue

        if field_name in entry:
            fixed_entry[field_name] = entry[field_name]
        elif field_name in SPLIT_FIELDS:
            split_field_names = SPLIT_FIELDS[field_name]
            interleaved_arr_len = len(entry[split_field_names[0]])
            val = []
            for i in range(interleaved_arr_len):
                for split_field_name in split_field_names:
                    val.append(entry[split_field_name][i])
            for l in range(len(val)):
                n = l % len(split_field_names)
                i = l // len(split_field_names)
                new_field_name = f"{split_field_names[n]}{i}"
                fixed_entry[new_field_name] = val[l]
        else:
            print("Missing field: {}".format(field_name))
    return fixed_entry

# %%
def gen_column_sql(field_name, field_value):
    field_type = type(field_value)
    if field_type == int:
        return f"`{field_name}` INT,"
    elif field_type == float:
        return f"`{field_name}` FLOAT,"
    elif field_type == str:
        # TODO maybe ascii vs unicode?
        return f"`{field_name}` TEXT,"
    else:
        print(f"Unknown type {field_type} for field {field_name}, skipping")
        return ""

# %%
def table_create(cursor, table_name, xdt_template_entry):
    sql = f"CREATE TABLE {table_name} ("
    sql += "id INT AUTO_INCREMENT PRIMARY KEY,"
    for field_name in xdt_template_entry:
        db_field_name = get_db_column_name(field_name)
        val = xdt_template_entry[field_name]
        sql += gen_column_sql(db_field_name, val)
    sql = sql[:-1] # remove trailing comma
    sql += ")"
    cursor.execute(sql)

# %%
def table_populate(cursor, table_name, table_entries):
    # generate the SQL first
    sql = f"INSERT INTO {table_name} ("
    template_entry = table_entries[0]
    for field_name in template_entry:
        db_field_name = get_db_column_name(field_name)
        sql += f"`{db_field_name}`,"
    sql = sql[:-1] # remove trailing comma
    sql += ") VALUES ("
    for field_name in template_entry:
        sql += f"%s,"
    sql = sql[:-1] # remove trailing comma
    sql += ")"
    
    vals = [table_entry_to_tuple(entry) for entry in table_entries]
    try:
        cursor.executemany(sql, vals)
    except Exception as e:
        print(sql)
        print(vals)
        raise e

# %%
def process_xdt_table(cursor, root, table_name, mappings):
    table = root[table_name]
    for subtable_name in tqdm(table, desc=table_name, total=len(table)):
        if subtable_name not in mappings[table_name]:
            print(f"No mapping found for {table_name}.{subtable_name}")
            raise Exception()
        db_table_name = mappings[table_name][subtable_name]
        with open(f"schema/{db_table_name}.json", 'r') as f:
            schema = json.load(f)
        #print(f"{subtable_name} => {db_table_name}")
        
        table_entries = table[subtable_name]
        if db_table_name == "CutSceneText":
            table_entries = handle_dict_table(table_entries, "m_iEvent", "m_TextElement")
        table_entries = [apply_schema(schema, entry) for entry in table_entries]
        table_entries = [flatten_table_entry(entry) for entry in table_entries]

        # clear the table
        drop_sql = f"DROP TABLE IF EXISTS {db_table_name}"
        cursor.execute(drop_sql)

        # create the table
        table_create(cursor, db_table_name, table_entries[0])
        table_populate(cursor, db_table_name, table_entries)

# %%
def main(conn, xdt_path):
    with open("mappings.json", 'r') as f:
        mappings = json.load(f)
    with open(xdt_path, 'r') as f:
        root = json.load(f)
    cursor = conn.cursor()
    for table_name in root:
        if "Table" in table_name:
            process_xdt_table(cursor, root, table_name, mappings)
    conn.commit()

def connect_to_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="mypassword",
        database="XDB"
    )

def prep_db():
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SET GLOBAL max_allowed_packet=1073741824")
    conn.commit()
    conn.close()

# %%
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 json2xdb.py <path to xdt file>")
        sys.exit(1)
    xdt_path = sys.argv[1]
    prep_db()
    conn = connect_to_db()
    main(conn, xdt_path)
    conn.close()

# %%



