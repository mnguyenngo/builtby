from mongoengine import connect

# import model class objects
# from models import Department, Employee, Role, Task


def init_db():
    # connect to local mongodb
    # port 27017 is default
    connect('seattle_land', host='localhost', port=27017)
