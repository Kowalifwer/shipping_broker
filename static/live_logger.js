// Description: This file handles the websocket data from the server and displays it on the page.

// Socket reconnection settings
CURRENT_ATTEMPT = 1;
MAX_ATTEMPTS = 10;
ATTEMPT_DELAY = 1000;
QUEUE_IDS = {};

window.addEventListener("load", function (event) {
    disable_button_actions();

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

    const PORT = document.getElementById("port").value;
    if (!PORT) {
        alert("No port found, error fetching.");
        return;
    }

    let socket;

    function socket_handler() {
        if (!socket) {
            socket = new WebSocket(`ws://localhost:${PORT}/ws/info/${user_id}/`);
        }

        socket.addEventListener("open", function () {
            CURRENT_ATTEMPT = 1;
            status.textContent = "Connected to server!";
            status.style.color = "green";

            enable_and_handle_button_actions();
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

    // This code is a bit tricky. The goal is to reconnect to the server socket, if the connection is lost, whilst showing an attempt counter to the user.
    // We reuse the socket_handler() function, to avoid code duplication and make sure all event listeners are set up correctly.
    // If we would have simply called the socket_handler() function again, it would have waited until the open event, and only run the code for the "open" event.
    // Therefore, there would be no way to show the user the reconnection attempt counter, since that code is triggered in the "close" and "error" events.

    // The solution is to create a new socket and manually check its state. If it's still in the CONNECTING state, we will show the user the reconnection attempt counter.
    // Once the socket is in the OPEN/connected state, we can continue the normal flow of the program by calling socket_handler() again.
    function handleSocketReconnect(msg) {
        // Attempt to reconnect to the server

        // Disable button actions until the socket is connected again
        disable_button_actions();

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

function enable_and_handle_button_actions() {
    let actionsWrapper = document.getElementById("actions-wrapper");

    //firstly, enable all buttons
    let buttons = actionsWrapper.querySelectorAll("button");
    buttons.forEach(button => {
        button.disabled = false;
        button.title = "";
    });

    // create a bubbler for the actionsWrapper, that listens to click event on each of its children (button elements)
    // if button is clicked - check its state. it represents a process that can either be started or stopped.
    // then trigger the appropriate action on the server.
    // Note that the click should only be counted, IF the button is NOT disabled.

    actionsWrapper.addEventListener("click", function (event) {
        let target = event.target;
        if (target.tagName == "BUTTON" && !target.disabled) {
            let start_url = target.dataset.startUrl;
            let stop_url = target.dataset.endUrl;
            let state = target.dataset.state;

            console.log(start_url, stop_url, state)

            let vebose_text = target.querySelector("span");

            // if state is "stopped" or does not exists - we need to start the process, by shooting a get request to the start_url
            // if state is "started" - we need to stop the process, by shooting a get request to the stop_url
            if (state == "stopped" || !state) {
                // set button to disabled, until the request is finished
                target.disabled = true;
                fetch(start_url)
                    .then(response => response.json())
                    .then(data => {
                        target.disabled = false;
                        if (data.error) {
                            alert(data.error);
                        } else {
                            target.dataset.state = "running";
                            vebose_text.textContent = "Stop";
                        }
                    });

            } else if (state == "running") {
                // set button to disabled, until the request is finished
                target.disabled = true;
                fetch(stop_url)
                    .then(response => response.json())
                    .then(data => {
                        target.disabled = false;
                        if (data.error) {
                            alert(data.error);
                        } else {
                            target.dataset.state = "stopped";
                            console.log(target.dataset.state)
                            vebose_text.textContent = "Start";
                            console.log(vebose_text.textContent)
                        }
                    });
            }
        }
    });
}

function disable_button_actions() {
    let actionsWrapper = document.getElementById("actions-wrapper");

    // disable all buttons
    let buttons = actionsWrapper.querySelectorAll("button");
    buttons.forEach(button => {
        button.disabled = true;
        button.title = "Please wait until the page is fully loaded.";
    });
}

function addMessageToChannel(channel_name, message) {
    let channel = document.getElementById(`info_area_channel_${channel_name}`);
    if (channel) {
        if (channel_name == "capacities") {
            // capacities will return a string with 2 number values, separated by a comma, i.e "1,2" or "8,10".
            // this represents the current queue capacity
            // we want to display this as a progress bar, with the first number being the current value, and the second number being the max value.
            let values = message.split(",");
            let current_value = parseInt(values[0]);
            let max_value = parseInt(values[1]);
            let q_id = values[2];

            let progress_bar_wrapper = document.getElementById(q_id);

            if (!progress_bar_wrapper) {
                // create a progress bar
                progress_bar_wrapper = document.createElement("div");
                progress_bar_wrapper.classList.add("progress-bar-wrapper");
                progress_bar_wrapper.id = q_id;

                let progress_bar = document.createElement("div");
                progress_bar.classList.add("progress-bar");
                progress_bar.setAttribute("role", "progressbar");
                progress_bar.setAttribute("aria-valuemin", "0");

                let p_title = document.createElement("p");

                progress_bar_wrapper.appendChild(p_title);
                progress_bar_wrapper.appendChild(progress_bar);

                channel.appendChild(progress_bar_wrapper);
            }

            let progress_bar = progress_bar_wrapper.querySelector(".progress-bar");
            let p_title = progress_bar_wrapper.querySelector("p");

            // update the progress bar
            progress_bar.setAttribute("aria-valuemax", max_value);
            progress_bar.setAttribute("aria-valuenow", current_value);
            progress_bar.style.width = `${(current_value / max_value) * 100}%`;

            // update the title of the progress bar
            p_title.textContent = `Queue capacity: ${current_value}/${max_value} items`;
        } else {
            let message_item = document.createElement("p");
            message_item.textContent = message;
            channel.appendChild(message_item);
        }
    } else {
        console.error(`Channel ${channel_name} not found.`);
    }
}
