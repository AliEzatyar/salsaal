/*
    This code enables achiving exact location of the user
*/
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (position) => {
            // Get coordinates
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            // Populate input fields
            console.log()
            if (!document.getElementById("id_lattitude").value) {
                document.getElementById("id_lattitude").value = latitude;
            }
            if (!document.getElementById("id_longtitiude").value) {
                document.getElementById("id_longtitiude").value = longitude;
            }
        },
        (error) => {
            // Handle errors
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    alert("User denied the request for Geolocation.");
                    break;
                case error.POSITION_UNAVAILABLE:
                    alert("Location information is unavailable.");
                    break;
                case error.TIMEOUT:
                    alert("The request to get user location timed out.");
                    break;
                case error.UNKNOWN_ERROR:
                    alert("An unknown error occurred.");
                    break;
            }
        }
    );
} else {
    alert("Geolocation is not supported by this browser.");
}