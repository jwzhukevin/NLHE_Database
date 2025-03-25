Clazz.declarePackage ("JSV.source");
Clazz.load (null, "JSV.source.JDXDecompressor", ["java.lang.Double", "JSV.common.Coordinate", "JU.Logger"], function () {
c$ = Clazz.decorateAsClass (function () {
this.xFactor = 0;
this.yFactor = 0;
this.deltaXcalc = 0;
this.nPoints = 0;
this.ich = 0;
this.lineNumber = 0;
this.t = null;
this.firstX = 0;
this.lastX = 0;
this.maxY = 4.9E-324;
this.minY = 1.7976931348623157E308;
this.debugging = false;
this.isNTUPLE = false;
this.xyCoords = null;
this.line = null;
this.lineLen = 0;
this.errorLog = null;
this.difVal = -2147483648;
this.lastDif = -2147483648;
this.dupCount = 0;
this.yval = 0;
this.firstLastX = null;
this.nptsFound = 0;
Clazz.instantialize (this, arguments);
}, JSV.source, "JDXDecompressor");
Clazz.defineMethod (c$, "getMinY", 
function () {
return this.minY;
});
Clazz.defineMethod (c$, "getMaxY", 
function () {
return this.maxY;
});
Clazz.makeConstructor (c$, 
function (t, firstX, xFactor, yFactor, lastX, nPoints, isNTUPLE) {
this.t = t;
this.isNTUPLE = isNTUPLE;
this.firstX = firstX;
this.xFactor = xFactor;
this.yFactor = yFactor;
this.lastX = lastX;
this.deltaXcalc = JSV.common.Coordinate.deltaX (lastX, firstX, nPoints);
this.nPoints = nPoints;
this.lineNumber = t.labelLineNo;
this.debugging = JU.Logger.isActiveLevel (6);
}, "JSV.source.JDXSourceStreamTokenizer,~N,~N,~N,~N,~N,~B");
Clazz.defineMethod (c$, "addPoint", 
 function (pt, ipt) {
if (ipt >= this.nPoints) return;
this.xyCoords[ipt] = pt;
this.firstLastX[1] = pt.getXVal ();
var y = pt.getYVal ();
if (y > this.maxY) this.maxY = y;
 else if (y < this.minY) this.minY = y;
if (this.debugging) this.logError ("Coord: " + ipt + pt);
}, "JSV.common.Coordinate,~N");
Clazz.defineMethod (c$, "decompressData", 
function (errorLog, firstLastX) {
this.errorLog = errorLog;
this.firstLastX = firstLastX;
if (this.debugging) this.logError ("firstX=" + this.firstX + " xFactor=" + this.xFactor + " yFactor=" + this.yFactor + " deltaX=" + this.deltaXcalc + " nPoints=" + this.nPoints);
this.xyCoords =  new Array (this.nPoints);
var difFracMax = 0.5;
var prevXcheck = 0;
var prevIpt = 0;
var x = this.firstX;
var lastLine = null;
var ipt = 0;
var haveWarned = false;
try {
while ((this.line = this.t.readLineTrimmed ()) != null && this.line.indexOf ("##") < 0) {
this.lineNumber++;
if (this.debugging) this.logError (this.lineNumber + "\t" + this.line);
if ((this.lineLen = this.line.length) == 0) continue;
this.ich = 0;
var isCheckPoint = (this.lastDif != -2147483648);
var xcheck = this.getValueDelim () * this.xFactor;
this.yval = this.getYValue ();
if (!isCheckPoint && ipt > 0) x += this.deltaXcalc;
var y = this.yval * this.yFactor;
var point =  new JSV.common.Coordinate ().set (x, y);
if (ipt == 0) {
firstLastX[0] = xcheck;
this.addPoint (point, ipt++);
} else if (ipt < this.nPoints) {
var lastPoint = this.xyCoords[ipt - 1];
if (isCheckPoint) {
this.xyCoords[ipt - 1] = point;
var lastY = lastPoint.getYVal ();
if (y != lastY) this.logError (lastLine + "\n" + this.line + "\nY-value Checkpoint Error! Line " + this.lineNumber + " for y=" + y + " yLast=" + lastY);
if (xcheck == prevXcheck || (xcheck < prevXcheck) != (this.deltaXcalc < 0)) {
this.logError (lastLine + "\n" + this.line + "\nX-sequence Checkpoint Error! Line " + this.lineNumber + " order for xCheck=" + xcheck + " after prevXCheck=" + prevXcheck);
}var xcheckDif = Math.abs (xcheck - prevXcheck);
var xiptDif = Math.abs ((ipt - prevIpt) * this.deltaXcalc);
var fracDif = Math.abs ((xcheckDif - xiptDif)) / xcheckDif;
if (this.debugging) System.out.println ("JDXD fracDif = " + xcheck + "\t" + prevXcheck + "\txcheckDif=" + xcheckDif + "\txiptDif=" + xiptDif + "\tf=" + fracDif);
if (fracDif > difFracMax) {
this.logError (lastLine + "\n" + this.line + "\nX-value Checkpoint Error! Line " + this.lineNumber + " expected " + xiptDif + " but X-Sequence Check difference reads " + xcheckDif);
}} else {
this.addPoint (point, ipt++);
}}prevIpt = (ipt == 1 ? 0 : ipt);
prevXcheck = xcheck;
while (this.ich < this.lineLen || this.difVal != -2147483648 || this.dupCount > 0) {
x += this.deltaXcalc;
if (!Double.isNaN (this.yval = this.getYValue ())) {
this.addPoint ( new JSV.common.Coordinate ().set (x, this.yval * this.yFactor), ipt++);
}}
if (!haveWarned && ipt > this.nPoints) {
this.logError ("! points overflow nPoints!");
haveWarned = true;
}lastLine = this.line;
}
} catch (ioe) {
if (Clazz.exceptionOf (ioe, java.io.IOException)) {
} else {
throw ioe;
}
}
this.nptsFound = ipt;
if (this.nPoints != ipt) {
this.logError ("Decompressor did not find " + this.nPoints + " points -- instead " + ipt + " xyCoords.length set to " + this.nPoints);
for (var i = ipt; i < this.nPoints; i++) this.addPoint ( new JSV.common.Coordinate ().set (0, 0), i);

}return (this.deltaXcalc > 0 ? this.xyCoords : JSV.common.Coordinate.reverse (this.xyCoords));
}, "JU.SB,~A");
Clazz.defineMethod (c$, "logError", 
 function (s) {
if (this.debugging) JU.Logger.debug (s);
System.err.println (s);
this.errorLog.append (s).appendC ('\n');
}, "~S");
Clazz.defineMethod (c$, "getYValue", 
 function () {
if (this.dupCount > 0) {
--this.dupCount;
this.yval = (this.lastDif == -2147483648 ? this.yval : this.yval + this.lastDif);
return this.yval;
}if (this.difVal != -2147483648) {
this.yval += this.difVal;
this.lastDif = this.difVal;
this.difVal = -2147483648;
return this.yval;
}if (this.ich == this.lineLen) return NaN;
var ch = this.line.charAt (this.ich);
switch (ch) {
case '%':
this.difVal = 0;
break;
case 'J':
case 'K':
case 'L':
case 'M':
case 'N':
case 'O':
case 'P':
case 'Q':
case 'R':
this.difVal = ch.charCodeAt (0) - 73;
break;
case 'j':
case 'k':
case 'l':
case 'm':
case 'n':
case 'o':
case 'p':
case 'q':
case 'r':
this.difVal = 105 - ch.charCodeAt (0);
break;
case 'S':
case 'T':
case 'U':
case 'V':
case 'W':
case 'X':
case 'Y':
case 'Z':
this.dupCount = ch.charCodeAt (0) - 82;
break;
case 's':
this.dupCount = 9;
break;
case '+':
case '-':
case '.':
case '0':
case '1':
case '2':
case '3':
case '4':
case '5':
case '6':
case '7':
case '8':
case '9':
case '@':
case 'A':
case 'B':
case 'C':
case 'D':
case 'E':
case 'F':
case 'G':
case 'H':
case 'I':
case 'a':
case 'b':
case 'c':
case 'd':
case 'e':
case 'f':
case 'g':
case 'h':
case 'i':
this.lastDif = -2147483648;
return this.getValue ();
case '?':
this.lastDif = -2147483648;
return NaN;
default:
this.ich++;
this.lastDif = -2147483648;
return this.getYValue ();
}
this.ich++;
if (this.difVal != -2147483648) this.difVal = this.getDifDup (this.difVal);
 else this.dupCount = this.getDifDup (this.dupCount) - 1;
return this.getYValue ();
});
Clazz.defineMethod (c$, "getDifDup", 
 function (i) {
var ich0 = this.ich;
this.next ();
var s = i + this.line.substring (ich0, this.ich);
return (ich0 == this.ich ? i : Integer.$valueOf (s).intValue ());
}, "~N");
Clazz.defineMethod (c$, "getValue", 
 function () {
var ich0 = this.ich;
if (this.ich == this.lineLen) return NaN;
var ch = this.line.charAt (this.ich);
var leader = 0;
switch (ch) {
case '+':
case '-':
case '.':
case '0':
case '1':
case '2':
case '3':
case '4':
case '5':
case '6':
case '7':
case '8':
case '9':
return this.getValueDelim ();
case '@':
case 'A':
case 'B':
case 'C':
case 'D':
case 'E':
case 'F':
case 'G':
case 'H':
case 'I':
leader = ch.charCodeAt (0) - 64;
ich0 = ++this.ich;
break;
case 'a':
case 'b':
case 'c':
case 'd':
case 'e':
case 'f':
case 'g':
case 'h':
case 'i':
leader = 96 - ch.charCodeAt (0);
ich0 = ++this.ich;
break;
default:
this.ich++;
return this.getValue ();
}
this.next ();
return Double.$valueOf (leader + this.line.substring (ich0, this.ich)).doubleValue ();
});
Clazz.defineMethod (c$, "getValueDelim", 
 function () {
var ich0 = this.ich;
var ch = '\u0000';
while (this.ich < this.lineLen && " ,\t\n".indexOf (ch = this.line.charAt (this.ich)) >= 0) this.ich++;

var factor = 1;
switch (ch) {
case '-':
factor = -1;
case '+':
ich0 = ++this.ich;
break;
}
ch = this.next ();
if (ch == 'E' && this.ich + 3 < this.lineLen) switch (this.line.charAt (this.ich + 1)) {
case '-':
case '+':
this.ich += 4;
if (this.ich < this.lineLen && (ch = this.line.charAt (this.ich)) >= '0' && ch <= '9') this.ich++;
break;
}
return factor * ((Double.$valueOf (this.line.substring (ich0, this.ich))).doubleValue ());
});
Clazz.defineMethod (c$, "next", 
 function () {
while (this.ich < this.lineLen && "+-%@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrs? ,\t\n".indexOf (this.line.charAt (this.ich)) < 0) this.ich++;

return (this.ich == this.lineLen ? '\0' : this.line.charAt (this.ich));
});
Clazz.defineMethod (c$, "getNPointsFound", 
function () {
return this.nptsFound;
});
Clazz.defineStatics (c$,
"allDelim", "+-%@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrs? ,\t\n",
"WHITE_SPACE", " ,\t\n");
});
