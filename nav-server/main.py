#    Copyright 2011 Trapez Breen
#
#    This file is part of Trap's Navigator.
#
#    Trap's Navigator is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Trap's Navigator is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Trap's Navigator.  If not, see <http://www.gnu.org/licenses/>.

from google.appengine.ext.webapp.util import run_wsgi_app
from navigator import app

run_wsgi_app(app)
