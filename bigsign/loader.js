// Various parts of this were borrowed and/or adapted from samples at
// http://www.boutell.com/newfaq/creating/ajaxfetch.html

var scoresReq;
var scoresUrl = "announcements.html";
var oldtext = ""
var timezone = ""

// Update the displayed scores
function updateScores(text) {
  var node, now;
  node = document.getElementById('announce');
  if (oldtext != text) {
    oldtext = text
    node.innerHTML = text;
  }
}

// Process a reply from the server with scores data
function processScoresReply() {
  if (scoresReq.readyState != 4)
    return;
  if (scoresReq.status == 200 && scoresReq.responseText)
    updateScores(scoresReq.responseText);
  scoresReq = null;
}

// Get an XMLHttpRequest object in a portable way.
function newRequest()
{
  var req;

  req = false;
  // For Safari, Firefox, and other non-MS browsers
  if (window.XMLHttpRequest) {
    try {
      req = new XMLHttpRequest();
    } catch (e) {
      req = false;
    }
  } else if (window.ActiveXObject) {
    // For Internet Explorer on Windows
    try {
      req = new ActiveXObject("Msxml2.XMLHTTP");
    } catch (e) {
      try {
        req = new ActiveXObject("Microsoft.XMLHTTP");
      } catch (e) {
        req = false;
      }
    }
  }
  return req;
}

// Request scores from the server
function requestScores() {
  setTimeout('requestScores()', 1000);
  if (scoresReq) return;

  scoresReq = newRequest()
  if (!scoresReq) return;

  try {
    scoresReq.open("GET",scoresUrl,true);
    scoresReq.setRequestHeader("Cache-Control", "no-cache");
    scoresReq.setRequestHeader("Pragma", "no-cache");
    scoresReq.setRequestHeader("Max-Age", "0");
    scoresReq.setRequestHeader("If-Modified-Since",
                               "Sat, 1 Jan 2000 00:00:00 GMT")
    scoresReq.onreadystatechange=processScoresReply;
    scoresReq.send(null);
  } catch (e) {
  }
}


// Called when we are first loaded
function onLoad() {
  setTimeout('requestScores()', 10);
}
