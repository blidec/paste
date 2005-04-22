from sqlobject import *

class TodoList(SQLObject):

    description = StringCol(notNull=True)
    items = MultipleJoin('TodoItem')

class TodoItem(SQLObject):

    todo_list = ForeignKey('TodoList')
    description = StringCol(notNull=True)
    done = BoolCol(notNull=True, default=False)