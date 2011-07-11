# -*- coding: utf-8 -*-

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

from google.appengine.ext import db


class User(db.Model):
    name = db.StringProperty(required=True)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    last_login = db.DateTimeProperty(required=True, auto_now=True)
    deactivated = db.BooleanProperty(required=True, default=False)
    uuid = db.StringProperty()
    
class Region(db.Model):
    name = db.StringProperty(required=True)
    cx = db.FloatProperty(required=True)
    cy = db.FloatProperty(required=True)
    course_count = db.IntegerProperty(required=True, default=0)
    
class Mark(db.Model):
    region = db.ReferenceProperty(Region)
    name = db.StringProperty()
    comment = db.TextProperty()
    x = db.FloatProperty(required=True)
    y = db.FloatProperty(required=True)
    gx = db.FloatProperty(required=True)
    gy = db.FloatProperty(required=True)    
    used = db.IntegerProperty(required=True, default=1)
    saved = db.BooleanProperty(required=True, default=False)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    deactivated = db.BooleanProperty(required=True, default=False)
    
class Course(db.Model):
    name = db.StringProperty(required=True)
    comment = db.TextProperty()
    start_region = db.ReferenceProperty(Region, collection_name="start_region_collection")
    end_region = db.ReferenceProperty(Region, collection_name="end_region_collection")
    last_modified = db.DateTimeProperty(required=True, auto_now=True)
    user = db.ReferenceProperty(User)
    marks = db.ListProperty(db.Key)
    turns = db.StringListProperty() 
    length = db.FloatProperty(required=True, default=0.0)
    public = db.BooleanProperty(required=True, default=True)
    type = db.StringProperty(required=True, choices=set(["RACE", "CRUISE"]))
    finished = db.IntegerProperty(required=True, default=0)
    saved = db.BooleanProperty(required=True, default=False)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    deactivated = db.BooleanProperty(required=True, default=False)
    version = db.IntegerProperty(required=True, default=1)
    
class State(db.Model):
    state = db.StringProperty(required=True, choices=set(["SAIL", "EDIT"]))
    course = db.ReferenceProperty(Course)
    mark = db.IntegerProperty(required=True, default=0)
    started = db.DateTimeProperty(required=True, auto_now_add=True)
    finished = db.DateTimeProperty(required=False)
    
class BlacklistUser(db.Model):
    user = db.ReferenceProperty(User)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    
class BlacklistCourse(db.Model):
    region = db.ReferenceProperty(Region)
    course = db.ReferenceProperty(Course)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    
class Setting(db.Model):
    name = db.StringProperty(required=True)
    value = db.StringProperty(required=True)