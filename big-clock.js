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

var options = new Map();
var maxLeaders = 3;
var cars = new Object;
var leaders = [];
var hb_timeout;

function process_opts() {
  var opts = new Map();
  var optlist = window.location.hash.replace(/^#/, '').split(';');
  optlist.forEach(function(val,index,a) {
    if (val != "") {
      var kv = val.split('=', 2);
      if (kv.length < 2) { kv[1] = 1 }
      opts.set(kv[0], kv[1]);
    }
  });
  options = opts;

  if (options.get("mode") == "tod") {
    document.getElementById("raceinfo").style.display = "none";
  } else {
    document.getElementById("bigtod").style.display = "none";
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
  process_opts();
  show_local_time();
  doconnect();
}
