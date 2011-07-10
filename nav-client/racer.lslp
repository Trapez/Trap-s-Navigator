//    Copyright 2011 Trapez Breen
//
//    This file is part of Trap's Navigator.
//
//    Trap's Navigator is free software: you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation, either version 3 of the License, or
//    (at your option) any later version.
//
//    Trap's Navigator is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU General Public License for more details.
//
//    You should have received a copy of the GNU General Public License
//    along with Trap's Navigator.  If not, see <http://www.gnu.org/licenses/>.

integer DEBUG = FALSE;

$import nav.lslm(DEBUG=DEBUG);


default {
    state_entry() {
    	set_texture("nav");
        owner = llGetOwner();
        get_user(owner);
        llOwnerSay(free_mem());
        //debug("Free memory: " + (string)llGetFreeMemory());
    }

    http_response(key request_id, integer status, list metadata, string body) {
        if (status == OK) {
            llOwnerSay(body);
            state main;
        }
        else if (status == NOT_ACCEPTABLE) {
        	llOwnerSay(body);
        }
        else {
        	llOwnerSay((string)status);
            llOwnerSay(body);
        }
    }

    on_rez(integer n) {
        llResetScript();
    }
}

state main {
    state_entry() {
    	set_texture("nav");
    	init();
    	//debug("editor state main");
        llOwnerSay("Ready.");
        llListen(0, "", owner, "");
        get_state();
    }
    
    touch_start(integer n) {
    	integer button = get_button();
    	//debug((string)button);
		if (button == MAIN)
			region_courses();
	}

    listen(integer chan, string name, key id, string option) {
		string k = choicek(option);
		//debug("k: " + k + " state: " + state_);
		//debug("option: " + option);
    	
    	if (k == "CANCEL") {
    		llOwnerSay("Ready.");
    		return;
    	}
		
    	if (!is_integer(option))
    		return;

    	if(k == "NO") {
    		state_ = "";
    		delete_state();
    		llOwnerSay("Ready.");
    		region_courses();
    	}
    	else if (k == "YES" && state_ == "SAIL")
    		state sail;
	    else if (k){
	    	courseid = k;
	    	get_course();
	    }
    }

    http_response(key request_id, integer status, list metadata, string body) {
    	//debug("body: " + body);
    	//debug("status: " + (string)status);
    	
    	if (region_courses_req_id == request_id || my_courses_req_id == request_id) {
    		if (status == OK)
				choose(SELECT_COURSE, llParseString2List(body, [";"], []), FALSE);
	        else
	            llOwnerSay(body);
    	}
	    else if (get_state_req_id == request_id) {
	    	if (status == OK) {
		    	list response = llParseString2List(body, [";"], []);
		    	string msg = llList2String(response, 0);
		    	state_ = llList2String(response, 1);
		    	current_mark = llList2Integer(response, 3);
		    	courseid = llList2String(response, 4);
		    	llOwnerSay(msg);
		    	choose(CHOOSE_OPTION, YES_NO_OPTIONS, FALSE);
	    	}
	    	else if (status == NO_RESPONSE)
	    		region_courses();
	    	else
	    		llOwnerSay(body);
	    }
	    else if (course_req_id == request_id) {
	    	//debug("state_:" + state_);
	    	if (status == OK) {
	    		llOwnerSay(body);
	    		state sail;
	    	}
	    	else
	    		llOwnerSay(body);
	    }
    }

    on_rez(integer n) {
        llResetScript();
    }
}


state sail {
    state_entry() {
    	//debug("state sail");
    	//debug("current_mark: " + (string)current_mark);
    	//debug("state: " + state_);
   		set_state("SAIL");
    }
   
    touch_start(integer n) {
    	integer button = get_button();
    	//debug("current_turn: " + current_turn);
    	if (current_turn == "FINISH" && button == NEXT)
   			delete_state();
   		else
			update_state(button);
    }

    http_response(key request_id, integer status, list metadata, string body) {
        if (set_state_req_id == request_id) {
        	if (status == OK) {
        		//debug("sailing");
        		//debug("current_course: " + (string)current_course);
        		//debug("current_mark: " + (string)current_mark);
        		update_state(MAIN);
        	}
        	else
        		llOwnerSay(body);	
        }
	    else if (update_state_req_id == request_id) {
	    	if (status == OK)
				set_mark(body);
	    	else 
	    		state main;
	    }
	    else if (delete_state_req_id == request_id) {
	    	llOwnerSay("\nSailing done.");
	    	state main;
	    }
    }
        
    on_rez(integer n) {
        llResetScript();
    }
}



