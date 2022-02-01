document.getElementById("psucontrol_meross_test_login").onclick = function update_info () {
	OctoPrint.simpleApiCommand(
        "psucontrol_meross",
        "try_meross_login",
        {
            "user_email": document.getElementById("psucontrol_meross_user_email").value,
            "user_password": document.getElementById("psucontrol_meross_user_password").value,
        }
    ).done(function(response){
        console.log(response);
    })
}