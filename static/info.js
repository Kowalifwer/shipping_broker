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
            handleError("Connection to server closed");
        });
    
        socket.addEventListener("error", function () {
            handleError("Error connecting to server");
        });
    
        function handleError(msg) {
            // attempt to reconnect, close previous socket if any and create a new one
            if (socket) {
                socket.close();
            }
        
            socket = new WebSocket(`ws://localhost:8000/ws/info/${user_id}/`);
        
            console.log(socket.readyState)
        
            function attemptReconnect() {
                // Close the WebSocket if it's still in the CONNECTING state after the timeout
                if (socket.readyState === WebSocket.CONNECTING) { 
                    if (CURRENT_ATTEMPT === 1) {
                        status.textContent = `${msg}. Will attempt to reconnect.`;
                        status.style.color = "red";
                    } else {
                        status.textContent = `${msg}. Reconnect attempt ${CURRENT_ATTEMPT} of ${MAX_ATTEMPTS}.`;
                        status.style.color = "orange";
                    }
                } else { 
                    // if the socket connected - stop the interval from attempting to reconnect.
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
            }
            
            // Run attemptReconnect until condition is met.
            let reconnectInterval = setInterval(() => {
                attemptReconnect();
                
                if (CURRENT_ATTEMPT > MAX_ATTEMPTS) {
                    clearInterval(reconnectInterval);

                    status.textContent = `Maximum number of attempts reached. Refreshing the page in 3 seconds....`;
                    status.style.color = "red";

                    socket.close();
                    
                    // refresh the page after 3 seconds
                    setTimeout(function () {
                        location.reload();
                    }, 3000);
                }

                CURRENT_ATTEMPT += 1;

            }, ATTEMPT_DELAY);
        }
    }

    socket_handler();
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
