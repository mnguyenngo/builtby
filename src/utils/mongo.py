from pymongo import MongoClient


def write_collection(dbname, coll, data, delete_existing=True):
    mc = MongoClient('localhost', 27017)
    db = mc[dbname]
    if delete_existing:
        if coll in db.collection_names():
            db.drop_collection(coll)
    collection = db[coll]
    collection.insert_many(data)


def write_doc(dbname, coll, doc):
    mc = MongoClient('localhost', 27017)
    db = mc[dbname]
    collection = db[coll]
    collection.insert_one(doc)


def load_collection(dbname, coll, to_json=False):
    """
    """
    mc = MongoClient('localhost', 27017)
    db = mc[dbname]
    collection = db[coll]
    if to_json:
        return list(collection.find())
    else:
        return collection  # type(collection) is mongo cursor


def delete_collection(dbname, coll):
    mc = MongoClient('localhost', 27017)
    db = mc[dbname]
    try:
        db.drop_collection(coll)
        print(f"Deleted {coll} collection from the {dbname} database")
    except Exception as exc:
        print(f"Encountered error when deleting {coll}")
        print(exc)
