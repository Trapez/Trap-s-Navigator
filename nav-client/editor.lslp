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

integer DEBUG = TRUE;

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
			choose(CHOOSE_OPTION, MAIN_OPTIONS_EDITOR, FALSE);
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
    		choose(CHOOSE_OPTION, MAIN_OPTIONS_EDITOR, FALSE);
    	}
    	else if (k == "YES" && state_ == "SAIL")
    		state sail;
    	else if (k == "YES" && state_ == "EDIT")
    		state edit;
		else if (k == "SAIL") {
			state_ = k;
    		region_courses();
		}
	    else if (k == "ADD")
	    	state new_course;
	    else if (k == "EDIT") {
	    	state_ = k;
	    	my_courses();
	    }
	    else if (k == "OPTIONS")
	    	state options;
	    else if (k){
	    	courseid = k;
	    	get_course();
	    }
    }

    http_response(key request_id, integer status, list metadata, string body) {
    	//debug("body: " + body);
    	//debug((string)status);

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
	    		choose(CHOOSE_OPTION, MAIN_OPTIONS_EDITOR, FALSE);
	    	else
	    		llOwnerSay(body);
	    }
	    else if (course_req_id == request_id) {
	    	//debug("state_:" + state_);
	    	if (status == OK) {
	    		llOwnerSay(body);
	    		if (state_ == "SAIL")
	    			state sail;
	    		else if (state_ == "EDIT")
	    			state edit;
	    	}
	    	else
	    		llOwnerSay(body);
	    }
    }

    on_rez(integer n) {
        llResetScript();
    }
}


state new_course {
    state_entry() {
        llListen(0, "", owner, "");
        choose("Will the course be public or private?", ["Public", "PUBLIC", "Private", "PRIVATE"], TRUE);
    }
    
    listen(integer chan, string name, key id, string option) {
    	string k = choicek(option);
    	debug("option: " + option + " k: " + k);
    	if (k == "CANCEL")
    		state main;

    	if (k == "PUBLIC" || k == "PRIVATE") {
    		course_access = k;
    		choose("\nWill the course be a race or a cruise course?", ["Race", "RACE", "Cruise", "CRUISE"], TRUE);
    	}
    	else if (k == "RACE" || k == "CRUISE") {
    		course_type = k;
    		llOwnerSay("\nEnter a name for this course:");
    	}
    	else if ((course_access == "PUBLIC" || course_access == "PRIVATE") && (course_type == "RACE" || course_type == "CRUISE"))
    		add_course(option);
    }
    
    http_response(key request_id, integer status, list metadata, string body) {
    	if (add_course_req_id == request_id) {
	    	llOwnerSay(body);
			if (status == OK)
	            state new_mark;
	        else
	            state main;
    	}
    }
    
    on_rez(integer n) {
        llResetScript();
    }
}


state new_mark {
    state_entry() {
        llListen(0, "", owner, "");
        llOwnerSay("\nGo to the start/startline and click the HUD, that will be the start mark.");
    }
    
    touch_start(integer n) {
        integer button = get_button();

		if (button == MAIN) {	
    		if (current_mark == 1)
				choose(HOW_TURN, ADD_MARK_OPTIONS, TRUE);
			else if (current_mark > 1)
				choose(HOW_TURN, ADD_MARK_OPTIONS + FINISH_MARK_OPTIONS, TRUE);
			else
				add_mark(current_mark, "START");
    	}
    }

    listen(integer chan, string name, key id, string option) {
    	string k = choicek(option);
    	//debug("option: " + option + " k: " + k);
    	    	
		if (k == "CANCEL")	
			state main;
			
		if (!is_integer(option))
			return;
    	
    	if (k == "FINISH")
    		course_done = TRUE;
    	if (in(ADD_MARK_OPTIONS + FINISH_MARK_OPTIONS, k))
    		add_mark(current_mark, k);
    }

    http_response(key request_id, integer status, list metadata, string body) {
    	//debug("status: " + (string)status + " body: " + body);
         if (save_course_req_id == request_id) {
         	debug("save");
            if (status == OK) {
                llOwnerSay(body);
                state main;
            }
            else {
                llOwnerSay(body);
                choose(TRY_AGAIN, TRY_CANCEL, TRUE);
            }
        }
        else if (add_mark_req_id == request_id) {
         	debug("add");
        	if (status == OK) {
        		marks_length = ++current_mark;
        		llOwnerSay(body);
        		if (course_done)
        			save_course();
        	}
        	else
        		llOwnerSay(body);
        }
    }
    
    on_rez(integer n) {
        llResetScript();
    }
}
    

state edit {
	state_entry() {
		current_region = llGetRegionName();
		//debug("state edit_courses");
		llListen(0, "", owner, "");
    	set_state("EDIT");
    }

    touch_start(integer n) {
    	integer button = get_button();
		//debug("button: " + (string)button + " edit_action: " + edit_action);
    	if (current_turn == "FINISH" && button == NEXT)
    		delete_state();
		else if (button == MAIN && (edit_action == "REPLM" || edit_action == "ADDM")) {
			newmark = llDetectedPos(0);
			choose(HOW_TURN, START_MARK_OPTIONS + ADD_MARK_OPTIONS + FINISH_MARK_OPTIONS, TRUE);
		}
		else
			update_state(button);
    }

    listen(integer chan, string name, key id, string option) {
    	string k = choicek(option);
    	//debug("option: " + option + " k: " + k);
    	if (k == "CANCEL" || k == "NO")
    		delete_state();
		
    	if (k == "DELC") {
    		edit_action = k;
    		choose(DELETE_COURSE, YES_NO_OPTIONS, FALSE);
    	}
    	else if (k == "RENC") {
    		edit_action = k;
    		llOwnerSay("\nEnter a new name for the course:");
    	}
    	else if (k == "TPP") {
    		edit_action = k;
			edit(edit_action);		
    	}
    	else if (k == "ANNC") {
    		edit_action = k;
    		llOwnerSay("\nEnter some description for this course:");
    	}
    	else if (k == "REPLM") {
    		edit_action = k;
    		llOwnerSay(CLICK_NEW_MARK);
    	}
    	else if (k == "DELM") {
    		edit_action = k;
    		choose(DELETE_MARK, YES_NO_OPTIONS, FALSE);
    	}
    	else if (k == "ADDM") {
    		edit_action = k;
    		llOwnerSay(CLICK_NEW_MARK);
    	}
    	else if (k == "GMN") {
    		edit_action = k;
    		llOwnerSay("\nEnter a name for this mark.");
    	}
    	else if (k == "ANNM") {
    		edit_action = k;
    		llOwnerSay("Enter some description for this mark:");
    	}
    	else if (edit_action == "RENC") {
    		newcoursename = option;
    		edit(edit_action);
    	}
    	else if (edit_action == "REPLM") {
    		newturn = k;
    		edit(edit_action);
    	}
    	else if (edit_action == "DELC" || (edit_action == "DELM" && k == "YES")) {
    		edit(edit_action);
    	}
    	else if (edit_action == "ADDM") {
    		newturn = k;
    		edit(edit_action);
    	}
    	else if (edit_action == "GMN") {
    		newmarkname = option;
    		edit(edit_action);
    	}
    	else if (edit_action == "ANNC" || edit_action == "ANNM") {
    		comment = option;
    		edit(edit_action);
    	}
    }
    
    http_response(key request_id, integer status, list metadata, string body) {
    	//debug("body: " + body);
		 if (course_req_id == request_id) {
			update_state(MAIN);
			choose(CHOOSE_OPTION, EDIT_OPTIONS, TRUE);
		}
		else if (set_state_req_id == request_id) {
			if (status == OK)
				update_state(MAIN);
		}
		else if (update_state_req_id == request_id) {
			if (status == OK) {
				set_mark(body);
				choose(CHOOSE_OPTION, EDIT_OPTIONS, TRUE);
			}
		}
        else if (delete_req_id == request_id || edit_req_id == request_id) { 
    		llOwnerSay(body);
    		delete_state();
        }
        else if (delete_state_req_id == request_id) {
        	llOwnerSay("\nEditing done.");
        	state main;
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


state options {
    state_entry() {
    	//debug("state options");
    	llListen(0, "", owner, "");
    	choose(CHOOSE_OPTION, SETTING_OPTIONS, TRUE);
    }
    
    touch_start(integer n) {
    	integer button = get_button();
    	
    	if (button == MAIN)
    		choose(CHOOSE_OPTION, SETTING_OPTIONS, TRUE);
    }
    
	listen(integer chan, string name, key id, string option) {
		string k = choicek(option);
		//debug("option: " + option + " k: " + k);
    	if (k == "CANCEL")
    		state main;
	
		if (k == "LBU")
			get_bl_users();
		else if (k == "TU")
			llOwnerSay("\nEnter a user name to blacklist:");
		else if (k == "LBC")
			get_bl_courses();
		else if (k == "TC")
			region_courses();
		else if (k == "EMC")
			export_courses(TRUE);
		else if (k == "EAC")
			export_courses(FALSE);
		else if (k != "" && is_integer(option)) {
			courseid = k;
			toggle_course();	
		}
		else if (k == "")
			toggle_user(option);
	}

    http_response(key request_id, integer status, list metadata, string body) {
		if (get_bl_users_req_id == request_id || get_bl_courses_req_id == request_id) {
			llOwnerSay(body);	
			choose(CHOOSE_OPTION, SETTING_OPTIONS, TRUE);
		}
		else if (toggle_user_req_id == request_id || toggle_course_req_id == request_id) {
			llOwnerSay(body);
			state main;
		}
		else if (region_courses_req_id == request_id) {
			choose("\nChoose a course to blacklist:", llParseString2List(body, [";"], []), TRUE);
		}
		else if (export_req_id == request_id) {
			llLoadURL(owner, "Course export.", body);
			state main;
		}
    }
    
    on_rez(integer n) {
        llResetScript();
    }
}
