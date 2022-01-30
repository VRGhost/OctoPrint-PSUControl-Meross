document.getElementById("update").onclick = function update_info () {
	OctoPrint.simpleApiCommand("psucontrol_meross", "try_meross_login")
        .done(function(response){
            console.log(response);
        })
}