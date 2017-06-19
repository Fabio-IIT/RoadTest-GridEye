
var host = window.location.host;
var ws = new WebSocket('ws://' + host + '/ws');
var $message = $('#received');

ws.onopen = function () {
    $message.attr("class", 'label label-success');
    $message.text('open');
};
ws.onmessage = function (ev) {
    $message.attr("class", 'label label-info');
    //$message.text(ev.data);
    try {
        var json = JSON.parse(ev.data);
        //var data=json.GE;
        var nlr = "NLR" in json ? json.NLR : 0;
        var lr = "LR" in json ? json.LR : 0;
        for (var i = 1; i <= 8; i++) {
            var checkBox = $("input[id=nlr" + i + "]");
            var set = ((nlr & (1 << (i - 1))) >> (i - 1)) == 1
            checkBox.prop("checked", set);
        }
        for (var i = 1; i <= 3; i++) {
            var checkBox = $("input[id=lr" + i + "]");
            var set = ((lr & (1 << (i - 1))) >> (i - 1)) == 1
            checkBox.prop("checked", set);
        }
        var tMax = "GE_MAX" in json ? json.GE_MAX.toFixed(2) : "N/A";
        var tMin = "GE_MIN" in json ? json.GE_MIN.toFixed(2) : "N/A";
        var tAvg = "GE_AVG" in json ? json.GE_AVG.toFixed(2) : "N/A";
      //  var ge = true;
     //   var checkBox = $("input[id=ge]");
        // if ("GE" in json) {
        //     if (!$.isArray(ge) || !ge.length) {
        //         //handler either not an array or empty array
        //         checkBox.prop("checked", false);
        //     }
        // } else {
        //     checkBox.prop("checked", true);
        // }
        $message.text("Max: " + tMax + "℃ - Min: " + tMin + "℃ - Avg: " + tAvg + "℃");
        var colours = json.GE_PIXEL_COLOUR;
        var rows = $('.row');
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var cols = $('.col', row);
            for (var j = 0; j < cols.length; j++) {
                $(cols[j]).css('background-color', "GE_PIXEL_COLOUR" in json ? colours[i * cols.length + j] : "#000");
                //$(cols[j]).text(data[i*cols.length+j].toFixed(2)).css("fontSize",12);
            }
        }
    } catch (err) {

    }
};
ws.onclose = function (ev) {
    $message.attr("class", 'label label-important');
    $message.text('closed');
};
ws.onerror = function (ev) {
    $message.attr("class", 'label label-warning');
    $message.text('error occurred');
};
var sendMessage = function (message) {
    //console.log("sending:" + message.data);
    ws.send(message.data);
};


// GUI Stuff


// send a command to the serial port
$("#cmd_send").click(function (ev) {
    ev.preventDefault();
    var cmd = $('#cmd_value').val();
    sendMessage({'data': cmd});
    $('#cmd_value').val("");
});
