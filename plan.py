# 1. Fetch emails. Add them to pipeline (with a producer-consumer pattern)
# 2. Process emails -> (THINK ABOUT PARALLELISM - either asyncio loop for api call or batch request to OpenAi API)

#     2.1. First, check if the email is already in the database (duplicates can happen), OR if it should be ignored (i.e. if it's a reply to an email that's already in the database)
#         2.1.1   Check by email_id FIRST, THEN by email_subject or other small fields. If it's a duplicate, skip it.
#         2.1.2   Think about how to ignore auto-replies, or spam, or stuff like delivery-has-failed emails

#     2.2    If it's not a duplicate, then process it
#         2.2.1   Extract the ship and cargo data from the email - via OpenAi API for now.
#         2.2.2   Add the ship and cargo data to the database. If the ship or cargo already exists, then handle udpates.

# 3. Go over all ships without cargo pairs, and find the best cargo for each ship
#     3.1. Find all cargoes that match the ship's criteria (i.e. port_from, port_to, sea_from, sea_to, month, quantity)
#     3.2. Have some simple scoring system, and allocate the top 5-10 cargos to the ship
#     3.3. Add the pairs to the database
#     3.4. ADD SEND EMAIL TASK to the pipeline. Pass all necessary data to the task (i.e the MongoDB object(s))

# 4. Email sending consumer
#     4.1. Constantly check the pipeline for new email sending tasks
#     4.2. For each email, generate the email body and send it to the relevant email address. (i.e. the email address of the ship owner)
#     4.3. Add references to the database for each email sent (figure out how to do this best)


# Notes:
# Think about how to allocate processing power - see if there are any bottlenecks, if so slow down the producer or consumer.
# Eg. Too much is used on processing emails, so slow down the producer.

# Think about how to handle errors - if an email fails to send, then what? Retry? Or just log it and move on?

# Think about how to handle updates - if a ship or cargo is updated, then what? Do we need to update the pairs? Or just leave them as is?

# Think about how to handle duplicates - if a ship or cargo is duplicated, then what? Do we need to update the pairs? Or just leave them as is?