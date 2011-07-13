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
    
    
from navigator import app
from flask import Response, request, url_for
from model import Course, Mark, User, State, Region, BlacklistUser, BlacklistCourse, Setting
import logging
from google.appengine.ext import db
from google.appengine.ext.db import Key
from google.appengine.api import urlfetch
from re import compile
from datetime import timedelta, datetime
from google.appengine.api import memcache
from traceback import print_exc
from google.appengine.ext.db import TransactionFailedError
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError
from math import sqrt, pow
from urllib import urlencode, quote
from hashlib import sha1
from StringIO import StringIO
from csv import writer
from uuid import uuid4
from utils import deserialize_entities, serialize_entities


DEBUG = True
SECRET_HASH = "4c4788654444e82f6b61f0bc05c0f871b2fbb74f";
PRODUCT = "TrapNav"
VERSION = "v0.40beta2"
MANDATORY = False
region_reg = compile(r'(?P<region>.+)\s+\((?P<cx>\d+),\s*(?P<cy>\d+)\)')
pos_reg = compile(r'\((?P<x>\d+\.\d+),\s*(?P<y>\d+\.\d+),\s*\d+\.\d+\)')
vector_reg = compile(r'<(?P<x>[\d\.]+),\s+(?P<y>[\d\.]+),\s+(?P<z>[\d\.]+)>')
version_reg = compile(r'v(?P<version>\d+\.\d+)(?P<beta>.*)')

sl_url = "slurl.com/secondlife/%s/128/128/25/"

CACHE_TIME = 3600
STATE_AGE = timedelta(0, CACHE_TIME)
TURNSD = {"START": "Start mark.", "CW": "Turn CW.", "CCW": "Turn CCW.", "FINISH": "Finish mark.", "WP": "Waypoint, sail by.", "GATEPASS": "Sail through gate.", "GATE": "Turn CW/CCW at gate."}
TURNS = ("START", "CW", "CCW", "GATE", "GATEPASS", "WP", "FINISH")
MIN_MARK_DIST = 64.0
CLOSE_DIST = 32.0
MIN_COURSE_LENGTH = 3

PREVIOUS = 1
NEXT = 3
DEFAULT_Z = 25.0


def get_region(s):
    m = region_reg.search(s)
    if m:
        return m.group("region"), float(m.group("cx")), float(m.group("cy"))
    
def get_position(s):
    m = pos_reg.search(s)
    if m:
        return float(m.group("x")), float(m.group("y"))
    
def vector2floats(s):
    m = vector_reg.search(s)
    if m:
        return float(m.group("x")), float(m.group("y")), float(m.group("z"))

def dec_mark(mark):
    dm = 0
    if not mark is None:
        if mark.used > 0: 
            mark.used -= 1
        if mark.used == 0:
            mark.deactivated = True
            dm = 1
        mark.put()
    return dm

def deactivate_course(course):
    dm = 0
    for mkey in course.marks:
        mark = Mark.get(mkey)
        dm += dec_mark(mark)
    course.deactivated = True
    course.parent().course_count -= 1
    course.put()
    return dm

def dist(x1, y1, x2, y2):
    return sqrt(pow(x2 - x1, 2) + pow(y2 - y1, 2))

def close(x1, y1, x2, y2):
    return dist(x1, y1, x2, y2) < CLOSE_DIST

def get_state(user):
    s = deserialize_entities(memcache.get("state-%s" % user.key().name()))
    if s is None:
        query = State.all()
        query.ancestor(user)
        query.filter("finished =", None)
        query.filter("started >", datetime.now() - STATE_AGE)
        s = query.get()
    return s
                
def get_user(user_key):
    user = deserialize_entities(memcache.get("user-%s" % user_key))
    if user is None:
        user = User.get_by_key_name(user_key)
    return user

def check_new_mark(region, course, turn, n, gx, gy):
    if course is None:
        return "\nMark was not saved, invalid course"
    
    if not turn in TURNS:
        return "\nMark was not saved, invalid turn."
    
    if turn == "START" and region.key() != course.start_region.key():
        return "\nMark was not saved, the start mark must be in the region of the course."
    
    if len(course.marks) > 0 and n == 0:
        next_mark = Mark.get(course.marks[n + 1])
        if close(gx, gy, next_mark.gx, next_mark.gy):
            return "\nMark %d was not saved, it is too close to mark %d. Please try again." % (n, n + 1)
    elif len(course.marks) > 0 and len(course.marks) == n:
        last_mark = Mark.get(course.marks[n - 1])
        if close(gx, gy, last_mark.gx, last_mark.gy):
            return "\nMark %d was not saved, it is too close to mark %d. Please try again." % (n + 1, n)
    elif len(course.marks) > n > 0:
        last_mark = Mark.get(course.marks[n - 1])
        next_mark = Mark.get(course.marks[n + 1])
        if close(gx, gy, last_mark.gx, last_mark.gy):
            return "Mark %d was not saved, it is too close to mark %d. Please try again." % (n + 1, n)
        if close(gx, gy, next_mark.gx, next_mark.gy):
            return "Mark %d was not saved, it is too close to mark %d. Please try again." % (n, n - 1)
        
def send_update(user_name, user_key):
    try:
        url = deserialize_entities(memcache.get("update.url"))
        if url is None:
            url = Setting.all().filter("name =", "update.url").get()
            memcache.set(key="update.url", value=serialize_entities(url), time=CACHE_TIME * 24)
        result = urlfetch.fetch(url, payload=urlencode([("userkey", user_key), ("product", PRODUCT), ("version", VERSION)]), method=urlfetch.POST)
        if result.status_code == 200:
            logging.info("Update %s sent to %s" % (VERSION, user_name))
        else:
            logging.error("Update %s for user %s, %s failed with status_code %d." % (VERSION, user_name, user_key, result.status_code))
    except Exception:
        if DEBUG: print_exc()
        logging.error("Update %s for user %s, %s failed." % (VERSION, user_name, user_key))
        
def course_length(course):
    distance = 0.0
    marks = {}
    for i in range(len(course.marks) - 1):
        mark1 = marks.get(course.marks[i], None) or Mark.get(course.marks[i])
        mark2 = marks.get(course.marks[i + 1], None) or Mark.get(course.marks[i + 1])
        distance += dist(mark1.gx, mark1.gy, mark2.gx, mark2.gy)
    return distance
        
@app.route("/user")
def user():    
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user_name = request.headers.get("X-SecondLife-Owner-Name")
    version = request.args.get("version")
    user_name_ = request.args.get("username")
    
    if user_name != user_name_:
        user_name = user_name_
    
    if not version or version < VERSION:
        send_update(user_name, user_key)
        if MANDATORY:
            return Response("Your Navigator is outdated, I'm sending you version %s." % VERSION, status=406)
        else:
            return Response("Your Navigator is outdated, I'm sending you version %s." % VERSION)
    
    user = User.get_or_insert(user_key, name=user_name)
    if not user is None:
        if user.name != user_name:
            user.name = user_name
    
        user.uuid = uuid4().hex
        user.put()
        memcache.set(key="user-%s" % user_key, value=serialize_entities(user), time=CACHE_TIME)
        return Response("Connected. Your navigator is up-to-date.")
    else:
        return Response("Unable to create a new user. Try rezzinga a new HUD.", status=500)
        
@app.route("/regioncourses")
def regioncourses():    
    region_name, _, _ = get_region(request.headers.get("X-SecondLife-Region"))
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key)
    region = Region.get_by_key_name(region_name)

    if not region is None:
        query = BlacklistUser.all(keys_only=True)
        query.ancestor(user)
        bl_users = [n for n in query]
        
        query = BlacklistCourse.all(keys_only=True)
        query.ancestor(user)
        bl_courses = [n for n in query]
        

        all_courses = []
        query = Course.all()
        query.ancestor(region.key())
        query.filter("saved =", True)
        query.filter("deactivated =", False)
        query.filter("public =", False)
        query.filter("user =", user.key())
        query.order("name")
        for course in query:
            all_courses.append("%s (%s by %s, private);%s" % (course.name, course.type.lower(), course.user.name, str(course.key())))

        courses = deserialize_entities(memcache.get("regioncourses-%s" % region_name))
        if courses is None:
            query = Course.all()
            query.ancestor(region.key())
            query.filter("saved =", True)
            query.filter("deactivated =", False)
            query.filter("public =", True)
            query.order("name")
            courses = [course for course in query]
            memcache.set(key="regioncourses-%s" % region_name, value=serialize_entities(courses), time=CACHE_TIME * 6)
        
        for course in courses:
            if course.user.key() not in bl_users and course.key() not in bl_courses:
                all_courses.append("%s (%s by %s);%s" % (course.name, course.type.lower(), course.user.name, str(course.key())))
    
        if all_courses:
            return Response(";".join(all_courses))  
        
    msg = "\nThere are no courses for region %s." % region_name
    regions = Region.all().filter("course_count >", 0).order("-course_count").fetch(10)
    msg += "\nTry one of these regions instead:\n" + "\n".join(["http://" + quote(sl_url % r.name) for r in regions])
    return Response(msg, status=406)  

@app.route("/course")
def course():
    course_key = request.args.get("courseid")
    region_name, _, _ = get_region(request.headers.get("X-SecondLife-Region"))
    region = Region.get_by_key_name(region_name)

    if not region is None and course_key:
        course = deserialize_entities(memcache.get("course-%s" % course_key))
        if course is None: 
            course = Course.get(course_key)
            memcache.set(key="course-%s" % course_key, value=serialize_entities(course), time=CACHE_TIME)
        if not course is None:
            if course.comment:
                return Response("\nAbout this course:\n" + course.comment)
            else:
                return Response()
        else:
            return Response("\nCourse not found.", status=404)
    else:
        return Response("\nCourse not found.", status=404)

@app.route("/addcourse", methods=["POST"])
def addcourse():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        course_name = request.args.get("coursename")
        access = request.args.get("access")
        type = request.args.get("type")
        region_name, cx, cy = get_region(request.headers.get("X-SecondLife-Region"))

        if not course_name.strip():
            return Response("Course was not saved, invalid course name.", status=406)
        
        query = Course.all()
        query.filter("saved =", False)
        query.filter("deactivated = ", False)
        query.filter("user =", user)
        
        dc = dm = 0
        for course in query:
            dm += deactivate_course(course)
            dc += 1
            
        def txn():
            region = Region.get_by_key_name(region_name)
            if region is None:
                region = Region(key_name=region_name, name=region_name, cx=cx, cy=cy)
                region.put()
            
            course = Course(name=course_name,
                            parent=region.key(),
                            start_region=region,
                            user=user.key(),
                            public=access == "PUBLIC",
                            type=type)

            course.put()
            memcache.set(key="course-%s" % user_key, value=serialize_entities(course), time=CACHE_TIME)
            
        db.run_in_transaction(txn)
        if dc:
            return Response("\nDeleted %d unsaved course(s) and %d mark(s). New course %s ready for region %s." % (dc, dm, course_name, region_name))
        else:
            return Response("\nNew course %s ready for region %s." % (course_name, region_name))
    except db.Timeout:
        msg = "\nNew course failed. The database timed out."
        logging.error(msg, status=500)
        return Response(msg)
    except CapabilityDisabledError:
        msg = "\nNew course failed. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nNew course failed. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        logging.error(str(e))
        if DEBUG: print_exc()
        return Response("\nNew course failed.", status=500)

@app.route("/savecourse", methods=["POST"])
def savecourse():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        region_name, cx, cy = get_region(request.headers.get("X-SecondLife-Region"))
        region = Region.get_or_insert(region_name, name=region_name, cx=cx, cy=cy)
        
        course = deserialize_entities(memcache.get("course-" + user_key))
        if course is None:
            query = Course.all()
            query.filter("user =", user.key())
            query.filter("saved =", False)
            query.filter("deactivated =", False)
            course = query.get()
            if not course:
                return Response("Course was not saved, something went wrong.", status=406)
                
        course.end_region = region
        marks = []
        for key in course.marks:
            mark = Mark.get(key)
            mark.saved = True
            marks.append(mark)
        db.put(marks)
            
        course.length = course_length(course)
        course.saved = True
        course.put()
        memcache.delete("course-" + user.key().name())
        return Response("\nCourse %s saved." % course.name)
    except db.Timeout:
        msg = "New course failed. The database timed out."
        logging.error(msg, status=500)
        return Response(msg)
    except CapabilityDisabledError:
        msg = "New course failed. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "New course failed. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        logging.error(str(e))
        if DEBUG: print_exc()
        return Response("New course failed.", status=500)

@app.route("/addmark", methods=["POST"])
def addmark():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        region_name, cx, cy = get_region(request.headers.get("X-SecondLife-Region"))
        x, y = get_position(request.headers.get("X-SecondLife-Local-Position"))
        turn = request.args.get("turn")
        n = int(request.args.get("n", 0))
        
        course = deserialize_entities(memcache.get("course-%s" % user_key))
        if course is None:
            query = Course.all()
            query.filter("user =", user.key())
            query.filter("saved =", False)
            query.filter("deactivated =", False)
            course = query.get()
            if not course:
                return Response("Course was not saved, something went wrong.", status=406)
            
        gx = cx + x
        gy = cy + y
        region = Region.get_or_insert(region_name, name=region_name, cx=cx, cy=cy)
        msg = check_new_mark(region, course, turn, n, gx, gy)
        if msg: return Response(msg, status=406)
        
        marks = deserialize_entities(memcache.get("marks-%s" % user_key))
        if marks is None:
            query = Mark.all()
            query.ancestor(user.key())
            query.filter("region =", region)
            query.filter("deactivated =", False)
            marks = [m for m in query]
            memcache.set(key="marks-%s" % user_key, value=serialize_entities(marks), time=CACHE_TIME)
            
        close_marks = sorted([(m, dist(gx, gy, m.gx, m.gy)) for m in marks if close(gx, gy, m.gx, m.gy)],
                             key=lambda o: o[1])

        if close_marks:
            mark = close_marks[0][0]
            mark.used += 1
            mark.put()
        else:
            mark = Mark(region=region, x=x, y=y, gx=gx, gy=gy, parent=user.key())
            mark.put()
        course.marks.append(mark.key())
        course.turns.append(turn)
        course.put()
        
        if not marks is None:
            marks.append(mark)
        else:
            marks = [mark]
        memcache.set(key="marks-%s" % user_key, value=serialize_entities(marks), time=CACHE_TIME)
        memcache.set(key="course-%s" % user_key, value=serialize_entities(course), time=CACHE_TIME)

        
        if turn == "START":
            s = "\nStart mark saved. Go to the next mark and click the HUD."
        elif turn == "FINISH":
            s = "\nFinish mark saved."
        else:
            s = "\nMark %d saved. Go to the next mark and click the HUD." % len(course.marks)
            
        if close_marks:
            d = dist(gx, gy, mark.gx, mark.gy)
            return Response(s + " This mark was merged with a predefined mark %.1fm. away." % round(d, 1))
        else:
            return Response(s)
    except db.Timeout:
        msg = "\nMark was not saved. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nMark was not saved. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nMark was not saved. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(e)
        return Response("\nMark was not saved. %s." % e, status=500)
    
@app.route("/mycourses")
def mycourses():
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key)
    region_name, _, _ = get_region(request.headers.get("X-SecondLife-Region"))
    region = Region.get_by_key_name(region_name)
    
    courses = []
    if not region is None:
        query = Course.all()
        query.ancestor(region)
        query.filter("user =", user.key())
        query.filter("saved =", True)
        query.filter("deactivated =", False)
    
        for course in query:
            courses.append("%s (%s by %s);%s" % (course.name, course.type.lower(), course.user.name, str(course.key())))
    logging.info(courses)
    if courses:
        return Response(";".join(courses))  
    else:
        return Response("\nYou have no courses in region %s." % region_name, status=406)    
        
@app.route("/edit", methods=["POST"])
def edit():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        region_name, cx, cy = get_region(request.headers.get("X-SecondLife-Region"))
        region = Region.get_or_insert(region_name, cx=cx, cy=cy)
        course_key = request.args.get("coursekey")
        action = request.args.get("action")
        course_name = request.args.get("coursename")
        mark_name = request.args.get("markname")
        mark = request.args.get("mark")
        turn = request.args.get("turn")
        comment = request.args.get("comment")
 
        if action in ("REPLM", "ADDM") and mark:
            x, y, _ = vector2floats(mark)
            gx = cx + x
            gy = cy + y
        
        course = Course.get(Key(course_key))
        if course is None or course.user.key() != user.key():
            return Response("\nSomething went wrong, course was not modified.")
        
        now = datetime.now()
        state = get_state(user)
        if state is None:
            raise ValueError("State missing!")
        
        memcache.delete("regioncourses-%s" % region_name)
        memcache.delete("course-%s" % course_key)
        i = state.mark
        if action == "DELC":
            deleted = deactivate_course(course)
            return Response("Course %s deleted. %d unused marks deleted." % (course.name, deleted))
        elif action == "RENC" and course_name:
            old_name = course.name
            course.name = course_name.strip()
            course.last_modified = now
            course.put()
            return Response("\nCourse %s was renamed to %s." % (old_name, course.name))
        elif action == "TPP":
            course.public = not course.public
            course.last_modified = now
            course.put()
            return Response("Course %s is now %s." % (course.name, "public" if course.public else "private"))
        elif action == "REPLM":
            msg = check_new_mark(region, course, turn, i, gx, gy)
            if msg: return Response(msg, status=406)

            mark = Mark.get(course.marks[i])
            mark.x = x
            mark.y = y
            mark.gx = gx
            mark.gy = gy
            mark.put()
            
            course.turns[i] = turn
            course.length = course_length(course)
            course.last_modified = now
            course.put()
            return Response("\nMark %d was replaced by a new mark." % (i + 1))
        elif action == "DELM":
            if len(course.marks) == MIN_COURSE_LENGTH:
                return Response("\nYou cannot delete a mark from a %d mark course, you can only replace them." % MIN_COURSE_LENGTH)
            elif 1 <= i < len(course.marks):
                mark = Mark.get(course.marks[i])
                del course.marks[i]
                del course.turns[i]
                dec_mark(mark)
                course.length = course_length(course)
                course.last_modified = now
                course.put()
                return Response("\nMark %d of course %s was deleted." % (i + 1, course.name))
            else:
                return Response("\nYou cannot delete the start/end mark, you can only replace them.")
        elif action == "ADDM":
            msg = check_new_mark(region, course, turn, i, gx, gy)
            if msg:
                return Response(msg, status=406)
        
            if 0 <= i < len(course.marks):
                mark = Mark(region=region, x=x, y=y, gx=gx, gy=gy, parent=user.key())
                mark.put()
                course.marks.insert(i + 1, mark.key())
                course.turns.insert(i + 1, turn)
                course.length = course_length(course)
                course.last_modified = now
                course.put()
                return Response("\nA %s mark was placed after mark %d of course %s." % (turn, i + 1, course.name))
            else:
                return Response("\nYou cannot add a mark after the finish mark.")
        elif action == "ANNC":
            course.comment = comment[:499]
            course.last_modified = now
            course.put()
            if len(comment) < 500:
                return Response("\nA comment was added to course %s." % course.name)
            else:
                return Response("\nThe comment was truncated to 500 characters and added to course %s." % course.name)
        elif action == "GMN" and mark_name:
            mark = Mark.get(course.marks[i])
            old_name = mark.name
            mark.name = mark_name.strip()
            mark.put()
            if old_name:
                return Response("\Mark %s was renamed to %s." % (old_name, mark.name))
            else:
                return Response("\nMark %d was named %s" % (i, mark.name))
        elif action == "ANNM":
            mark = Mark.get(course.marks[i])
            mark.comment = comment[:499]
            mark.put()
            if len(comment) < 500:
                return Response("\nA comment was added to mark %d of course %s." % (i + 1, course.name))
            else:
                return Response("\nThe comment was truncated to 500 characters and added to mark %d of course %s." % (i + 1, course.name))
    except db.Timeout:
        msg = "\nCourse was not modified. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nCourse was not modified. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nCourse was not modified. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(e)
        return Response("\nCourse was not modified. %s." % e, status=500)

@app.route("/getstate")
def getstate():
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key)
    
    s = get_state(user)
    if not s is None:
        state = "editing" if s.state == "EDIT" else "sailing"
        msg = "\nYou were %s course %s from region %s a while ago, would you like to continue?" % (state, s.course.name, s.course.start_region.name)
        memcache.set(key="state-%s" % user_key, value=serialize_entities(s), time=CACHE_TIME)
        return Response(";".join((msg, s.state, s.course.name, str(s.mark), str(s.course.key()))))
    else:
        return Response(status=204)
    
@app.route("/updatestate", methods=["POST"])
def updatestate():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        button = int(request.args.get("button", 0))

        s = get_state(user)
        if not s is None and button:
            lm = len(s.course.marks)
            if button == PREVIOUS and s.mark > 0:
                s.mark -= 1
            elif button == NEXT and s.mark < lm - 1:
                s.mark += 1
                
            s.started = datetime.now()
            s.put()
            memcache.set(key="state-%s" % user_key, value=serialize_entities(s), time=CACHE_TIME)
            mark = Mark.get(s.course.marks[s.mark])
            turn = s.course.turns[s.mark]
            if mark.name:
                msg = "\n%s\nMark %d of %d. %s\n%s" % (mark.name, s.mark + 1, lm, TURNSD[turn] if turn in TURNSD else "missing turn", mark.comment if mark.comment else "")
            else:
                msg = "\nMark %d of %d. %s\n%s" % (s.mark + 1, lm, TURNSD[turn] if turn in TURNSD else "missing turn", mark.comment if mark.comment else "")
            return Response(",".join((str(s.mark), str(mark.x), str(mark.y), mark.region.name, turn, msg)))
        else:
            return Response(status=204)
    except db.Timeout:
        msg = "\nState was not updated. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nState was not updated. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nState was not updated. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nState was not updated. %s." % e, status=500)

@app.route("/setstate", methods=["POST"])
def setstate():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        state = request.args.get("state")
        course_id = request.args.get("courseid")
    
        course = Course.get(Key(course_id))
        
        s = State(parent=user,
                  course=course,
                  state=state,
                  started=datetime.now())
        s.put()
        memcache.set(key="state-%s" % user_key, value=serialize_entities(s), time=CACHE_TIME)
        return Response()
    except db.Timeout:
        msg = "\nState was not saved. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nState was not saved. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nState was not saved. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nState was not saved. %s." % e, status=500)
    
@app.route("/deletestate", methods=["DELETE"])
def deletestate():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        
        query = State.all()
        query.ancestor(user)
        query.filter("finished =", None)
        for s in query:
            s.finished = datetime.now()
            if s.state == "SAIL":
                s.course.finished += 1
                s.course.put()
            elif s.state == "EDIT":
                s.course.version += 1
                s.course.put()
            s.put()
        memcache.delete("state-" + user_key)
        return Response()
    except db.Timeout:
        msg = "\nState was not deleted. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nState was not deleted. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nState was not deleted. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nState was not deleted. %s." % e, status=500)

@app.route("/getblacklistedusers")
def getblacklistedusers ():
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key)
    
    query = BlacklistUser.all()
    query.ancestor(user)
    result = sorted([User.get(n.user.key()).name for n in query])
    
    if result:
        return Response("\nBlacklisted users:\n" + "\n".join(result))
    else:
        return Response("\nYour user blacklist is empty.")     

@app.route("/blacklistuser")
def blacklistuser():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        toggle_user_name = request.args.get("username")
    
        query = User.all()
        query.filter("name =", toggle_user_name)
        toggle_user = query.get()
        
        if toggle_user is None:
            return Response("\nThere is no user `%s` in the navigator." % toggle_user_name, status=404)
        
        query = BlacklistUser.all()
        query.ancestor(user)
        query.filter("user =", toggle_user.key())
        wl_user = query.get()
        
        if wl_user is None:
            blu = BlacklistUser(parent=user, user=toggle_user)
            blu.put()
            return Response("\nUser `%s` was added to your blacklist." % toggle_user_name)
        else:
            wl_user.delete()
            return Response("\nUser `%s` was removed from your blacklist." % toggle_user_name)
    except db.Timeout:
        msg = "\nUser was not blacklisted. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nUser was not blacklisted. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nUser was not blacklisted. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nUser was not blacklisted. %s." % e, status=500)
        
@app.route("/getblacklistedcourses")
def getblacklistedcourses():
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key)
    region_name, _, _ = get_region(request.headers.get("X-SecondLife-Region"))
    region = Region.get_by_key_name(region_name)
    
    query = BlacklistCourse.all()
    query.ancestor(user)
    query.filter("region =", region)
    result = sorted(["%s (by %s)" % (n.course.name, n.course.user.name) for n in query])
    
    if result:
        return Response("\nBlacklisted courses:\n" + "\n".join(result))
    else:
        return Response("\nYour course blacklist is empty.")  
    
@app.route("/blacklistcourse")
def blacklistcourse():
    try:
        user_key = request.headers.get("X-SecondLife-Owner-Key")
        user = get_user(user_key)
        course_id = request.args.get("courseid")
        region_name, _, _ = get_region(request.headers.get("X-SecondLife-Region"))
        region = Region.get_by_key_name(region_name)
        
        course = Course.get(Key(course_id))
        
        query = BlacklistCourse.all()
        query.ancestor(user)
        query.filter("course =", course.key())
        bl_course = query.get()
        
        if bl_course is None:
            blc = BlacklistCourse(parent=user, course=course, region=region)
            blc.put()
            return Response("\nCourse `%s` was added to your blacklist." % course.name)
        else:
            bl_course.delete()
            return Response("\nCourse `%s` was removed from your blacklist." % course.name)
    except db.Timeout:
        msg = "\nCourse was not blacklisted. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nCourse was not blacklisted. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nCourse was not blacklisted. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nCourse was not blacklisted. %s." % e, status=500)

@app.route("/register", methods=["POST"])
def register(self, **kw):
    try:
        secret = request.args.get("secret")
        url = request.args.get("url")
        
        if sha1(secret).hexdigest() == SECRET_HASH and url:
            s = Setting.all().filter("name =", "update.url").get()
            if not s is None:
                s.value = url
                s.put()
            else:
                s = Setting(name="update.url", value=url)
                s.put()
            memcache.set(key="update.url", value=serialize_entities(url), time=CACHE_TIME * 24)
            logging.info("New url recieved: %s" % url)
        return Response("URL recieved.")
    except db.Timeout:
        msg = "\nUrl was not saved. The database timed out."
        logging.error(msg)
        return Response(msg, status=500)
    except CapabilityDisabledError:
        msg = "\nUrl was not saved. Database could not be written to."
        logging.error(msg)
        return Response(msg, status=500)
    except TransactionFailedError:
        msg = "\nUrl was not saved. Transaction failed."
        logging.error(msg)
        return Response(msg, status=500)
    except Exception, e:
        if DEBUG: print_exc()
        logging.error(str(e))
        return Response("\nUrl was not saved. %s." % e, status=500)

@app.route("/export/<int:mine>")
@app.route("/export/<int:mine>/<uuid>")
def export(mine=0, uuid=""):
    user_key = request.headers.get("X-SecondLife-Owner-Key")
    user = get_user(user_key) if not user_key is None else None
        
    if not user is None:
        csv = deserialize_entities(memcache.get("csv-user_key-%d-%s" % (mine, user_key)))
        if not csv is None:
#            logging.info("csv-user_key-%d-%s" % (mine, user_key))
#            logging.info("using cache: user_key")
            return Response(url_for("export", _external=True, mine=str(mine), uuid=user.uuid))

    if uuid:
        csv = deserialize_entities(memcache.get("csv-uuid-%d-%s" % (mine, uuid)))
        if not csv is None:
#            logging.info("csv-uuid-%d-%s" % (mine, uuid))
#            logging.info("using cache: uuid")
            return Response(csv, mimetype="application/excel")  
        else:
            return Response(status=204)
        
#    logging.info("not using cache: %d %s" % (mine, uuid))

    query = Course.all()
    query.filter("saved =", True)
    query.filter("deactivated =", False)
    if mine:
        query.filter("user = ", user.key())
    else:        
        query.filter("public =", True)

    marks = {}
    buffer = StringIO()
    w = writer(buffer, delimiter=";") 
    w.writerow(("Region", "Name", "Comment", "Creator", "Creator key", "Created", "Last modified", "Public", "Type",
                "Mark: Region, Turn, Name, Comment, Local x, Local y, Global x, Gobal y, Created"))
    
    for course in query:
        row = [course.start_region.name,
               course.name,
               course.comment,
               course.user.name,
               course.user.key().name(),
               course.created.strftime("%Y-%m-%d %H:%M:%S"),
               course.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
               "Yes" if course.public else "No",
               course.type.capitalize()]

        for i, mkey in enumerate(course.marks):
            if mkey in marks:
                mark = marks[mkey]
            else:
                mark = Mark.get(mkey)
                marks[mark.key()] = mark
            row.append(",".join((mark.region.name, course.turns[i], mark.name or "", mark.comment or "",
                                 str(mark.x), str(mark.y), str(mark.gx), str(mark.gy), 
                                 mark.created.strftime("%Y-%m-%d %H:%M:%S"))))
        w.writerow(row)

    value = serialize_entities(buffer.getvalue())
    memcache.set_multi({"user_key-%d-%s" % (mine, user_key): value,
                        "uuid-%d-%s" % (mine, user.uuid): value}, key_prefix="csv-", time=CACHE_TIME * 24)
       
#    logging.info(url_for("export", _external=True, mine=str(mine), uuid=user.uuid))
    return Response(url_for("export", _external=True, mine=str(mine), uuid=user.uuid))
