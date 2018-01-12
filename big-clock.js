/*
 * Copyright (c) 2016-2017 Jeffrey Hutzelman.
 * All Rights Reserved.
 * See LICENSE for licensing terms.
 */
var f_topdiv   = document.getElementById("topdiv");
var f_run      = document.getElementById("run");
var f_tod      = document.getElementById("tod");
var f_tod2     = document.getElementById("tod2");
var f_date     = document.getElementById("date");
var f_flag     = document.getElementById("flag");
var f_laps     = document.getElementById("laps");
var f_laps2go  = document.getElementById("laps2go");
var f_elapsed  = document.getElementById("elapsed");
var f_timeleft = document.getElementById("timeleft");
var f_leaders  = document.getElementById("leaders");
var f_message  = document.getElementById("message");
var f_error    = document.getElementById("error");

var f_version  = document.getElementById("version");
var f_options  = document.getElementById("options");
var f_v_html   = document.getElementById("version_html");
var f_v_css    = document.getElementById("version_css");
var f_v_js     = document.getElementById("version_js");
var f_v_srv    = document.getElementById("version_srv");
var f_v_opts   = document.getElementById("version_opts");

var css_version = "";
var js_version = "1.1-@@@@@@-@@@@@@";
var data_port = "9999";

var timezone = "";
var server_tz = "";
var display_mode;
var display_modes = [ "raceinfo", "bigtod" ]
var maxLeaders = 3;
var cars = new Object;
var leaders = [];
var tod_is_local = false;
var opts_changed = false;
var hb_timeout;
var server_error = "";

function getCookie(name) {
    function escape(s) { return s.replace(/([.*+?\^${}()|\[\]\/\\])/g, '\\$1'); };
    var match = document.cookie.match(RegExp('(?:^|;\\s*)' + escape(name) + '=([^;]*)'));
    return match ? match[1] : null;
}

function process_opts(optstr) {
  if (optstr == null) {
    optstr = window.location.hash.replace(/^#/, '');
  }
  f_v_opts.textContent = optstr;
  opts_changed = true;

  var opts = new Map();
  var optlist = optstr.split(';');
  optlist.forEach(function(val,index,a) {
    if (val != "") {
      var kv = val.split('=', 2);
      if (kv.length < 2) { kv[1] = 1 }
      opts.set(kv[0], kv[1]);
    }
  });

  if (opts.has("mode")) display_mode = opts.get("mode");
  else display_mode = "raceinfo";
  for (var mode of display_modes) {
    var e = document.getElementById(mode);
    if (display_mode == mode) e.style.display = "block";
    else                      e.style.display = "none";
  }

  if (opts.has("tz")) {
    timezone = opts.get("tz");
    if (tod_is_local) show_local_time();
  }

  f_topdiv.className = "top";
  if (opts.has("display")) {
    f_topdiv.classList.add(opts.get("display"));
  }

  if (opts.has("version")) {
    f_version.style.visibility = "visible";
    f_options.style.visibility = "visible";
  } else {
    f_version.style.visibility = "hidden";
    f_options.style.visibility = "hidden";
  }
}

function show_local_time () {
  tod_is_local = true;
  var now = new Date();
  var todopts = { hour12:false, hour:'2-digit', minute:'2-digit' };
  var dayopts = { year:'numeric', month:'long', day:'numeric', weekday:'long' };
  if (timezone != "") {
    todopts['timeZone'] = timezone;
    dayopts['timeZone'] = timezone;
  } else if (server_tz != "") {
    todopts['timeZone'] = server_tz;
    dayopts['timeZone'] = server_tz;
  }
  f_tod2.textContent  = now.toLocaleTimeString(undefined, todopts);
  f_date.textContent = now.toLocaleDateString(undefined, dayopts);
}

function showMessage(msg) {
  f_message.textContent = msg
}

function showError(msg) {
  if (msg == '') {
    f_error.style.display = "none";
    f_message.style.display = "inline";
  } else {
    f_error.textContent = msg;
    f_message.style.display = "none";
    f_error.style.display = "inline";
  }
}

function reconnect(s) {
  console.log("Server heartbeat timeout");
  s.close(4000, "Server heartbeat timeout");
}

function heartbeat(e,s) {
  showError(server_error);
  if (hb_timeout !== undefined) {
    window.clearTimeout(hb_timeout);
  }
  hb_timeout = window.setTimeout(reconnect, 3000, s);
}

function doconnect() {
    try {
        var host = "ws://" + window.location.hostname + ":" + data_port + "/";
        console.log("Host:", host);
        var s = new WebSocket(host);
        s.onopen = function (e) {
            console.log("Socket opened.");
            heartbeat(e,s);
            s.send(JSON.stringify(['%U', window.navigator.userAgent]));
            s.send(JSON.stringify(['%V', f_v_html.textContent,
                                  css_version, js_version]));
        };
        s.onclose = function (e) {
            console.log("Socket closed.");
            showError("Server connection lost");
            show_local_time();
            window.setTimeout(doconnect, 3000);
        };
        s.onmessage = function (e) {
            heartbeat(e,s);
            console.log("Socket message:", e.data);
            if (opts_changed) {
              s.send(JSON.stringify(['%O', f_v_opts.textContent]));
              opts_changed = false;
            }
            if (e.data == "ping") {
              s.send("pong");
              return;
            }
            fields = JSON.parse(e.data);
            //f_run.textContent = fields[0];
            /* Possible field formats:
             *   $A,regno,car,txno,first,last,nat,classno
             *   $COMP,regno,car,classno,first,last,nat,addl
             *   $B,runid,description
             *   $C,classno,description
             *   $E,setting,value
             *   $F,laps2go,timeleft,tod,elapsed,flag
             *   $G,pos,regno,laps,time
             *   $H,pos,regno,bestlap,besttime
             *   $I,tod,date (init/reset)
             *   $J,regno,laptime,time
             *
             *   :V,server-version
             */
            if (fields[0] == '$A') {
              cars[fields[1]] = fields[2];
            } else if (fields[0] == '$B') {
              /* Run info: $B,id,description */
              f_run.textContent = fields[2];
            } else if (fields[0] == '$F') {
              /* flag info: $F,laps2go,remaining,tod,elapsed,flag */
              if (fields[1] == 9999) f_laps2go.textContent = '';
              else                   f_laps2go.textContent = fields[1];
              f_timeleft .textContent = fields[2];
              f_tod      .textContent = fields[3];
              f_tod2     .textContent = fields[3];
              f_elapsed  .textContent = fields[4];
              tod_is_local = false;
              //f_flag     .textContent = fields[5];
            } else if (fields[0] == '$G') {
              /* race info: $G,pos,regcode,laps,time */
              if (fields[1] == 1) f_laps.textContent = fields[3];
              if (fields[1] <= maxLeaders) {
                leaders[fields[1]-1] = cars[fields[2]];
                var leaderstr = '';
                for (var i = 0; i < maxLeaders; i++) {
                  if (leaders[i] === undefined) break;
                  if (i > 0) leaderstr += ', ';
                  leaderstr += leaders[i];
                }
                f_leaders.textContent = leaderstr;
              }
            } else if (fields[0] == '$I') {
              tod_is_local = false;
              f_tod.textContent = fields[1];
              f_tod2.textContent = fields[1];
              var date = new Date(fields[2]);
              f_date.textContent = date.toLocaleDateString(undefined, {
                weekday: 'long', year: 'numeric',
                month: 'long', day: 'numeric' });
              f_run      .textContent = '';
              //f_flag     .textContent = '';
              f_laps     .textContent = '';
              f_laps2go  .textContent = '';
              f_elapsed  .textContent = '--:--:--';
              f_timeleft .textContent = '--:--:--';
              f_leaders  .textContent = '';
              cars = new Object;
              leaders = [];
            } else if (fields[0] == ':E') {
              server_error = fields[1];
              showError(server_error);
            } else if (fields[0] == ':M') {
              showMessage(fields[1]);
            } else if (fields[0] == ':OPT') {
              process_opts(fields[1]);
            } else if (fields[0] == ':R') {
              document.location.reload(true)
            } else if (fields[0] == ':TZ') {
              server_tz = fields[1];
              if (tod_is_local) show_local_time();
            } else if (fields[0] == ':V') {
              f_v_srv.textContent = fields[1];
            }
        };
        s.onerror = function (e) {
            console.log("Socket error:", e);
        };
    } catch (ex) {
        console.log("Socket exception:", ex);
        window.setTimeout(doconnect, 3000);
    }
}

function onLoad() {
  /* Extract the version string components.
   * The CSS document's version is embedded in a style on the topdiv, and
   * our (JS) version is embedded in a variable declaration above.
   * The server version is not updated here; instead, it is set when the
   * server sends it to us.
   */
  var topstyle = window.getComputedStyle(f_topdiv);
  css_version = topstyle.getPropertyValue('--bigclock-version').trim();
  if (css_version.startsWith('"') && css_version.endsWith('"')) {
    css_version = css_version.slice(1, -1);
  }
  f_v_css.textContent  = css_version;
  f_v_js.textContent   = js_version;

  var port = getCookie('bigclock_port');
  if (port != null) data_port = port;

  process_opts();
  show_local_time();
  doconnect();
}
