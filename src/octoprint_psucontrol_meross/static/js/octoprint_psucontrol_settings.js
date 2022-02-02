function psucontrol_meross_show_error(msg) {
    var el = $('#psucontrol_meross_error')
    if(msg)
    {
        el.text(msg);
        el.show();
    }
    else
    {
        el.hide();
    }
}

function psucontrol_meross_show_comm() {
    $('#psucontrol_meross_loading').show()
}

function psucontrol_meross_hide_comm() {
    $('#psucontrol_meross_loading').hide()
}

document.getElementById("psucontrol_meross_test_login").onclick = function() {
    psucontrol_meross_show_comm();

	OctoPrint.simpleApiCommand(
        "psucontrol_meross",
        "try_login",
        {
            "user_email": document.getElementById("psucontrol_meross_user_email").value,
            "user_password": document.getElementById("psucontrol_meross_user_password").value,
        }
    ).done(function(response){
            psucontrol_meross_show_error(response.error);
            console.log(response);
    }).always(psucontrol_meross_hide_comm)
}

document.getElementById("psucontrol_meross_device_list").onclick = function() {
    psucontrol_meross_show_comm();
    OctoPrint.simpleApiCommand(
        "psucontrol_meross",
        "list_devices",
        {
            "user_email": document.getElementById("psucontrol_meross_user_email").value,
            "user_password": document.getElementById("psucontrol_meross_user_password").value,
        }
    ).done(function(response){
        psucontrol_meross_show_error(response.error);
        if(response.error) {
            return;
        }
        // No errors reported.
        var dropdown = $("#psucontrol_meross_device_list");
        var old_val = dropdown.val();
        var old_dev_val_present = false;

        dropdown.empty();
        $.each(response.rv, function() {
            dropdown.append($("<option />").val(this.dev_id).text(this.name));
            old_dev_val_present = old_dev_val_present || (this.dev_id == old_val)
        });

        if(old_val && !old_dev_val_present) {
            // Append a mock option for the original value
            dropdown.append($("<option />").val(old_val).text("Unknown device (" + old_val + ")"));
        }

        dropdown.val(old_val);
    }).always(psucontrol_meross_hide_comm);
}