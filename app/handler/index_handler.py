from dataclasses import dataclass
from flask import render_template
from injector import inject
import logging
logger = logging.getLogger(__name__)
@inject
@dataclass
class IndexHandler:
    def index(self):
        return render_template("index.html")
