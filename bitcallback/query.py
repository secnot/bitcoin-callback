"""
query

Custom paginated query for sqlalchemy
"""
from math import ceil
from sqlalchemy.orm import Query
from flask import abort



class Pagination(object):
    """Paginated query response class"""

    def __init__(self, query, page, per_page, total, items):
        """
        query (Query): query that generated this
        page (int): page number
        per_page (int): items per page
        total (int): Total numbers of items
        items (list): list of items in the page
        """
        #
        self.query = query

        # Current page number
        self.page = page

        # Number of items per page
        self.per_page = per_page

        # total number of items matching query
        self.total = total

        # items for cureent page
        self.items = items

    @property
    def pages(self):
        """The total number of pages"""
        if self.per_page == 0:
            pages = 0
        else:
            pages = int(ceil(self.total/float(self.per_page)))

        return pages

    @property
    def prev_num(self):
        """previous page number, None if it doesn't exist"""
        if not self.has_prev:
            return None
        return self.page-1

    @property
    def next_num(self):
        """next page number, None if it does't exist"""
        if not self.has_next:
            return None
        return self.page+1

    @property
    def has_prev(self):
        """True if there is a previous page"""
        return self.page > 1

    @property
    def has_next(self):
        """True if there is a next page"""
        return self.page < self.pages



class PaginatedQuery(Query):
    """Custom paginated query"""

    def paginate(self, page=1, per_page=10):
        """Request only a page of the results"""

        if per_page < 1 or page < 1:
            abort(404)
        items = self.limit(per_page).offset((page-1)*per_page).all()
        if not items and page != 1:
            abort(404)

        total = self.order_by(None).count()
        return Pagination(self, page, per_page, total, items)


