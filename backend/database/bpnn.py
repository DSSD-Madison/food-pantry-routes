import sqlite3

conn = sqlite3.connect("bpnn_database.db")
cursor = conn.cursor()

def read_from_database(table_name):
    # Read from the table
    
    query = f"SELECT * FROM {table_name};"
    cursor.execute(query)
    rows = cursor.fetchall()

    for row in rows:
        print (row)


def insert_location_deliverers(name, location):

    cursor.execute(f"INSERT INTO deliverers (Name) VALUES (?);", (name, ))
    conn.commit()

    # Getting the primary id of the deliverer just added
    cursor.execute("SELECT id FROM deliverers WHERE Name = ?;", (name, ))
    deliverer_id = cursor.fetchone()[0]
    print("deliverer_id: ", deliverer_id)

    cursor.execute("INSERT INTO locations VALUES (?, ?);", (location, deliverer_id))
    conn.commit()

# read_from_database("deliverers")
insert_location_deliverers("Name30", "location412")