# %%
import json
import sys
from tqdm import tqdm
import mysql.connector

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
    for (i, subtable_name) in tqdm(enumerate(table), desc=table_name, total=len(table)):
        db_table_name = mappings[table_name][i]
        #print(f"{subtable_name} => {db_table_name}")
        
        table_entries = table[subtable_name]
        if db_table_name == "CutSceneText":
            table_entries = handle_dict_table(table_entries, "m_iEvent", "m_TextElement")
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

# %%
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 json2xdb.py <path to xdt file>")
        sys.exit(1)
    xdt_path = sys.argv[1]
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="mypassword",
        database="tabledata"
    )
    main(conn, xdt_path)

# %%



