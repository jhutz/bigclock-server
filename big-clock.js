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
var f_error    = document.getElementById("error");

var f_version  = document.getElementById("version");
var f_options  = document.getElementById("options");
var f_v_html   = document.getElementById("version_html");
var f_v_css    = document.getElementById("version_css");
var f_v_js     = document.getElementById("version_js");
var f_v_srv    = document.getElementById("version_srv");
var f_v_opts   = document.getElementById("version_opts");

var js_version = "0.9";

var display_mode;
var display_modes = [ "raceinfo", "bigtod" ]
var maxLeaders = 3;
var cars = new Object;
var leaders = [];
var hb_timeout;

function process_opts() {
  var opts = new Map();
  var optstr = window.location.hash.replace(/^#/, '');
  f_v_opts.textContent = optstr;

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
  var now = new Date();
  f_tod2.textContent  = now.toLocaleTimeString(undefined, {
    hour12: false, hour: '2-digit', minute: '2-digit'
  });
  f_date.textContent = now.toLocaleDateString(undefined, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

function reconnect(s) {
  console.log("Server heartbeat timeout");
  s.close(4000, "Server heartbeat timeout");
}

function heartbeat(e,s) {
  f_error.style.visibility = "hidden";
  if (hb_timeout !== undefined) {
    window.clearTimeout(hb_timeout);
  }
  hb_timeout = window.setTimeout(reconnect, 3000, s);
}

function doconnect() {
    try {
        var host = "ws://" + window.location.hostname + ":9876/stuff";
        console.log("Host:", host);
        var s = new WebSocket(host);
        s.onopen = function (e) {
            console.log("Socket opened.");
            heartbeat(e,s);
        };
        s.onclose = function (e) {
            console.log("Socket closed.");
            f_error.style.visibility = "visible";
            show_local_time();
            window.setTimeout(doconnect, 3000);
        };
        s.onmessage = function (e) {
            heartbeat(e,s);
            console.log("Socket message:", e.data);
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
              f_elapsed  .textContent = '';
              f_timeleft .textContent = '';
              f_leaders  .textContent = '';
              cars = new Object;
              leaders = [];
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
   * The HTML document's last-modified timestamp must be fetch early, before
   * we make any document changes, or we'll get a bogus time.  The actual
   * document version is embedded in the document and need not be updated.
   *
   * The CSS document's version is embedded in a style on the topdiv, and
   * our (JS) version is embedded in a variable declaration above.  We cannot
   * obtain last-modified timestamps for these documents, but the server may
   * embed them in the reported documents at some point in the future.
   *
   * The server version is not updated here; instead, it is set when the
   * server sends it to us.
   */
  var html_mod = new Date(document.lastModified);
  var html_version = html_mod.toLocaleString(undefined, {
    year: 'numeric', month: 'numeric', day: 'numeric',
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  var topstyle = window.getComputedStyle(f_topdiv);
  var css_version = topstyle.getPropertyValue('--bigclock-version')
  f_v_html.textContent = html_version;
  f_v_css.textContent  = css_version;
  f_v_js.textContent   = js_version;

  process_opts();
  show_local_time();
  doconnect();
}
