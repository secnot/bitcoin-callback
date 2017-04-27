## CRITICAL

- Callback_task saves callbacks to db when first received and after each update
- Bitcoin_task Reconnect to bitcoind when connection is lost


## FEATURES

- Load unacknowledged callbacks from db during initialization
- Load active subscriptions from db during initialization

## FEATURES
- Make subscription callback_url optional (when a default url is provided)
- API view tests
