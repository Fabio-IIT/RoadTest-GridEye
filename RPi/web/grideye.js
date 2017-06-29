/**
 * Created by fabio on 27/06/17.
 */
$(document).ready(function () {
    var width = 64;
    var height = 64;
    var bw_width = 8;
    var bw_height = 8;
    $('input[type=checkbox]').onoff();
    for (var r = 1; r <= height; r++) {
        var row = $('<div class="row"></div>');
        $('#grid').append(row);
        for (var i = 1; i <= width; i++) {
            var pixel = $('<div class="col"></div>').data('row', r).data('col', i);
            row.append(pixel);
        }
    }
    for (var r = 1; r <= bw_height; r++) {
        var row_bw = $('<div id="row-bw-' + r + '" class="row-bw"></div>');
        $('#grid-bw').append(row_bw);
        for (var i = 1; i <= bw_width; i++) {
            var pixel_bw = $('<div id="col-bw-' + i + '" class="col-bw"></div>').data('row-bw', r).data('col-bw', i);
            row_bw.append(pixel_bw);
            pixel_bw.on('click', null, {x: r, y: i}, function (ev) {
                sendMessage({'data': JSON.stringify({'X': ev.data.x, 'Y': ev.data.y})});
            });
        }
    }

    var host = window.location.host;
    var ws = new WebSocket('ws://' + host + '/ws');
    var $message = $('#received');

    ws.onopen = function () {
        $message.attr("class", 'label label-success');
        $message.text('Starting Up...');
        sendMessage({'data':JSON.stringify({'SRC': 'WEB','CMD':'UPDATE_UI'})});
    };

    ws.onmessage = function (ev) {
        $message.attr("class", 'label label-info');
        try {
            var json = JSON.parse(ev.data);
            if ("ALARM" in json) {
                var alarmBox = $(".alarm-box");
                if (json.ALARM == "SET") {
                    alarmBox.addClass("blink")
                } else if (json.ALARM == "RESET") {
                    alarmBox.removeClass("blink")
                }
            }
            if ("CELL" in json) {
                var x = json.X;
                var y = json.Y;
                var cellSet = (json.CELL == "SET");
                var cell = $('#row-bw-' + x + ' #col-bw-' + y);
                if (cellSet) {
                    if (!cell.hasClass('active')) {
                        cell.addClass('active');
                    }
                } else {
                    if (cell.hasClass('active')) {
                        cell.removeClass('active');
                    }
                }
            }
            if ("MODE" in json){
                switch (json.MODE){
                    case 1:$('#det-mode-abs').prop('checked',true);
                            break;
                    case 2:$('#det-mode-diff').prop('checked',true);
                            break;
                    case 3:$('#det-mode-both').prop('checked',true);
                            break;
                    case 4:$('#det-mode-any').prop('checked',true);
                            break;
                }
            }
            if ("NLR" in json) {
                var nlr = json.NLR;
                for (var i = 1; i <= 8; i++) {
                    var checkBox = $("input[id=nlr" + i + "]");
                    var value = ((nlr & (1 << (i - 1))) >> (i - 1)) == 1;
                    checkBox.prop("checked", value);
                }
            }
            if ("LR" in json) {
                var lr = json.LR;
                for (var i = 1; i <= 3; i++) {
                    var checkBox = $("input[id=lr" + i + "]");
                    var value = ((lr & (1 << (i - 1))) >> (i - 1)) == 1
                    checkBox.prop('checked', value);
                }
            }
            if ("GE" in json) {
                var tMax = "GE_MAX" in json ? json.GE_MAX.toFixed(2) : "N/A";
                var tMin = "GE_MIN" in json ? json.GE_MIN.toFixed(2) : "N/A";
                var tMean = "GE_AVG" in json ? json.GE_AVG.toFixed(2) : "N/A";
                var tMdn = "GE_MDN" in json ? json.GE_MDN.toFixed(2) : "N/A";
                var tStd = "GE_STD" in json ? json.GE_STD.toFixed(2) : "N/A";
                $message.text("Max: " + tMax + "℃ - Min: " + tMin + "℃ - Mean: " + tMean + "℃ - Med: " + tMdn + "℃ - Std Dev: " + tStd + "℃");
                var myRainbow = new Rainbow();
                //myRainbow.setNumberRange(tMin*100,tMax*100);
                myRainbow.setNumberRange(tMin * 100, tMax * 100);
                myRainbow.setSpectrum("#5e4fa2", "#3288bd", "#66c2a5", "#abdda4", "#e6f598", "#ffffbf", "#fee08b", "#fdae61", "#f46d43", "#d53e4f", "#9e0142");
                var rows = $('.row');
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var cols = $('.col', row);
                    for (var j = 0; j < cols.length; j++) {
                        $(cols[j]).css('background-color', myRainbow.colourAt(json.GE[i * cols.length + j] * 100));
                        //$(cols[j]).text(json.GE[i*cols.length+j].toFixed(2)).css("fontSize",12).css("font-family","Verdana, Geneva, sans-serif");
                    }
                }
            }
            if ("GE_BINARY" in json) {
                var bw = json.GE_BINARY;
                var rows = $('.row-bw');
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var cols = $('.col-bw', row);
                    for (var j = 0; j < cols.length; j++) {
                        $(cols[j]).css('background-color', bw[i * cols.length + j] == 1 ? "#FFFFFF" : "#000");
                        if ("GE_TEMP" in json) {
                            $(cols[j]).text(json.GE_TEMP[i * cols.length + j].toFixed(2)).css("fontSize", 12).css("font-family", "Verdana, Geneva, sans-serif").css("color", "red");
                        }
                    }
                }
            }
        } catch (err) {

        }
    };
    ws.onclose = function (ev) {
        $message.attr("class", 'label label-important');
        $message.text('Sensor disconnected');
    };
    ws.onerror = function (ev) {
        $message.attr("class", 'label label-warning');
        $message.text('Error occurred');
    };
    var sendMessage = function (message) {
//console.log("sending:" + message.data);
        ws.send(message.data);
    };

    $('input[name=detection-mode]').attr("disabled",true);

    $('.reset-button').click(function (ev) {
        ev.preventDefault();
        sendMessage({'data': JSON.stringify({'ALARM': 'RESET'})});
    });

    $('.reload-button').click(function (ev) {
        ev.preventDefault();
        sendMessage({'data': JSON.stringify({'BACKGROUND': 'RESET'})});
    });

    for (var i = 1; i <= 8; i++) {
        $('input[id=nlr' + i + ']').click({value: i}, function (ev) {
            ev.preventDefault();
            var statusStr = $(this).is(':checked') ? 'ON' : 'OFF';
            sendMessage({'data': JSON.stringify({'NLR': ev.data.value, 'STATUS': statusStr})});
        });
    }
    for (var i = 1; i <= 3; i++) {
        $("input[id=lr" + i + "]").click({value: i}, function (ev) {
            ev.preventDefault();
            var statusStr = $(this).is(':checked') ? 'ON' : 'OFF';
            sendMessage({'data': JSON.stringify({'LR': ev.data.value, 'STATUS': statusStr})});
        });
    }
});