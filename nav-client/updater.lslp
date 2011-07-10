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

//string SERVER = "";
string SERVER = "http://trapsnavigator.appspot.com";
integer DEBUG = FALSE;

$import utils.lslm(DEBUG=DEBUG, SERVER=SERVER);

string secret = "";
//4c4788654444e82f6b61f0bc05c0f871b2fbb74f
string url;

key url_req_id;
key reg_req_id;


register(string url) {
	llInstantMessage(llGetOwner(), "Registering with the server...");
	reg_req_id = POST("/register", ["secret", secret, "url", url]);
}

init() {
	llOwnerSay("Requesting URL...");
	llSetTimerEvent(3600);
	url_req_id = llRequestURL();
}


default {	
    state_entry() {
        init();
    }
    
    touch_end(integer num_detected) {
    	if (llDetectedKey(0) == llGetOwner())
    		init();
    }
    
    timer() {
    	url_req_id = llRequestURL();
    }
    
    http_request(key request_id, string method, string body) {
    	if (url_req_id == request_id) {
	    	if (method == URL_REQUEST_GRANTED) {
	    		if (url) llReleaseURL(url);
	    		url = body;
	    		register(url);
	    	}
	    	else if (method == URL_REQUEST_DENIED)
	    		llOwnerSay("No URL granted.");
	    	else llOwnerSay(body);
    	}
    	else if (method == "POST") {
    		list qs = llParseString2List(body, ["&"], []);
    		list userkeyp = llParseString2List(llList2String(qs, 0), ["="], []);
    		list productp = llParseString2List(llList2String(qs, 1), ["="], []);
    		list versionp = llParseString2List(llList2String(qs, 2), ["="], []);
    		string userkey = llList2String(userkeyp, 1);
    		string product = llList2String(productp, 1);
    		string version = llList2String(versionp, 1);
    		
    		llGiveInventory(userkey, product + " " + version);
    		llInstantMessage(llGetOwner(), product + " " + version + " sent to " + userkey);
    		llHTTPResponse(request_id, OK, "");
    	}
    }
    
    http_response(key request_id, integer status, list metadata, string body) {
    	if (reg_req_id == request_id) {
    		if (status == OK)
    			llOwnerSay(body);
    	}
    }
    
    changed(integer change) {
    	if (change & CHANGED_REGION_START)
    		llResetScript();
    }
    
    on_rez(integer n) {
        llResetScript();
    }
}
