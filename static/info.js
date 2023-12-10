// Description: This file handles the websocket data from the server and displays it on the page.

// Socket reconnection settings
CURRENT_ATTEMPT = 1;
MAX_ATTEMPTS = 10;
ATTEMPT_DELAY = 1000;

window.addEventListener("load", function (event) {
    let user_id = document.getElementById("user_id").value;
    if (!user_id) {
        alert("No user id found, error fetching.");
        return;
    }

    let channels = document.getElementById("channels").value;
    let channels_list = JSON.parse(channels);
    if (!channels_list) {
        alert("No channels found, error fetching.");
        return;
    }

    const status = document.getElementById("status");
    if (!status) {
        alert("No status found, error fetching.");
        return;
    }

    let socket;

    function socket_handler() {
        if (!socket) {
            socket = new WebSocket(`ws://localhost:8000/ws/info/${user_id}/`);
        }

        socket.addEventListener("open", function () {
            CURRENT_ATTEMPT = 1;
            status.textContent = "Connected to server!";
            status.style.color = "green";
        });
    
        socket.addEventListener("message", function (event) {
            let socket_data = event.data;
            let json_data = JSON.parse(socket_data);
    
            for (let key in json_data) {
                addMessageToChannel(key, json_data[key]);
            }
        });
    
        socket.addEventListener("close", function () {
            handleSocketReconnect("Connection to server closed");
        });
    
        socket.addEventListener("error", function () {
            handleSocketReconnect("Error connecting to server");
        });
    }

    socket_handler();


    // This code is a bit tricky. The goal is to reconnect to the server if the connection is lost, whilst showing an attempt counter to the user.
    // We reuse the socket_handler() function, to avoid code duplication and make sure all event listeners are set up correctly.
    // If we would have simply called the socket_handler() function again, it would have waited until the open event, and only run the code for the "open" event.
    // Therefore, there would be no way to show the user the reconnection attempt counter, since that code is triggered in the "close" and "error" events.

    // The solution is to create a new socket and manually check its state. If it's still in the CONNECTING state, we will show the user the reconnection attempt counter.
    // Once the socket is in the OPEN/connected state, we can continue the normal flow of the program by calling socket_handler() again.
    function handleSocketReconnect(msg) {
        // Attempt to reconnect to the server

        // Make sure to close existing socket if it exists
        if (socket) {
            socket.close();
        }
        // Create a new socket. Note that after creation, it will go into the CONNECTING state. We then manually wait until it's in the OPEN state, and run socket_handler() again.
        socket = new WebSocket(`ws://localhost:8000/ws/info/${user_id}/`);
        
        // Setup a reconnection attempt at ATTEMPT_DELAY intervals. Will run until the socket gets connected again, OR until MAX_ATTEMPTS is reached.
        let reconnectInterval = setInterval(() => {
            
            // Close the WebSocket if it's still in the CONNECTING state after the timeout
            if (socket.readyState == WebSocket.CONNECTING) { 
                if (CURRENT_ATTEMPT == 1) {
                    status.textContent = `${msg}. Will attempt to reconnect.`;
                    status.style.color = "red";
                } else {
                    status.textContent = `${msg}. Reconnect attempt ${CURRENT_ATTEMPT} of ${MAX_ATTEMPTS}.`;
                    status.style.color = "orange";
                }
            } else { 
                // If the socket finally connected - stop the interval from repeated attempts, and continue with the normal flow of the program.
                if (socket.readyState == WebSocket.OPEN) {
                    clearInterval(reconnectInterval);

                    // The goal of this code is to make sure that our next iteration of the socket_handler, which has an "open" event listener, is called to continue the normal flow of the program.
                    // Therefore, we will first call socket_handler, and then send the "open" event to the socket after a short delay. (remember, the async/non-blocking nature of setTimeout allows us to do this)
                    setTimeout(() => {
                        socket.dispatchEvent(new Event("open"));
                    }, ATTEMPT_DELAY/2);

                    socket_handler();
                }
            }
            
            // After each attempt, increment the attempt counter.
            CURRENT_ATTEMPT += 1;
            
            // After each attempt, check if we have reached the maximum number of attempts. If we have, we will stop trying to reconnect and close the socket and refresh the page.
            if (CURRENT_ATTEMPT > MAX_ATTEMPTS) {
                // Stop the interval from repeated attempts
                clearInterval(reconnectInterval);

                status.style.color = "red";

                socket.close();
                
                let secs = 5;
                // Refresh the page after 5 seconds, with a countdown user can see.
                let countdownInterval = setInterval(function () {
                    if (secs == 0) {
                        clearInterval(countdownInterval);
                        location.reload();
                    }
                    status.textContent = `Maximum number of attempts reached. Refreshing the page in ${secs} seconds....`;
                    secs -= 1;
                }, 1000);
            }

        }, ATTEMPT_DELAY);
    }
});

function connectToWebSocketWithRetry() {
    let user_id = document.getElementById("user_id").value;
    if (!user_id) {
        alert("No user id found, error fetching.");
        return;
    }

    let channels = document.getElementById("channels").value;
    let channels_list = JSON.parse(channels);
    if (!channels_list) {
        alert("No channels found, error fetching.");
        return;
    }

    const socket = new WebSocket(`ws://localhost:8000/ws/info/${user_id}/`);

    socket.addEventListener("open", function (event) {
        CURRENT_ATTEMPT = 1;
        const status = document.getElementById("status");
        status.textContent = "Connected to server!";
        status.style.color = "green";
    });

    socket.addEventListener("message", function (event) {
        let socket_data = event.data;
        let json_data = JSON.parse(socket_data);

        for (let key in json_data) {
            addMessageToChannel(key, json_data[key]);
        }
    });
}



function addMessageToChannel(channel_name, message) {
    let channel = document.getElementById(`info_area_channel_${channel_name}`);
    if (channel) {
        let message_item = document.createElement("p");
        message_item.textContent = message;
        channel.appendChild(message_item);
    } else {
        console.error(`Channel ${channel_name} not found.`);
    }
}
