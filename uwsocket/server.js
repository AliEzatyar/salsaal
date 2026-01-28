import uWS from "uWebSockets.js";
import { createClient } from 'redis';
import jwt from 'jsonwebtoken';
import { configDotenv } from "dotenv";
// loading .env variables into process.env
configDotenv()

const PORT = process.env.SERVER_PORT || 3000;

const djangoServerUrl = process.env.DJANGO_SERVER_URL
const redisUrl = process.env.REDIS_URL

// getting public key for verifying user's jwt tokens
let JWT_PUBLIC_KEY;
try {
    const res = await fetch(djangoServerUrl + "/jwtks/");
    if (res.ok) {
        JWT_PUBLIC_KEY = await res.text();
        console.log("JWT public key loaded successfully");
    } else {
        console.error("Failed to fetch JWT public key:", res.status, res.statusText);
        JWT_PUBLIC_KEY = null;
    }
} catch (error) {
    console.error("Error fetching JWT public key:", error);
    JWT_PUBLIC_KEY = null;
}


// creating and connecting redis publisher and subscriber
const redisPub = createClient({
    url: redisUrl,  // <- connection details
})
const redisSub = createClient({
    url: redisUrl,  // <- connection details
})
try {
    await redisPub.connect();
    await redisSub.connect();
} catch (error) {
    console.error("Failed to connect to Redis:", error);
    process.exit(1);
}


redisPub.on("error", (err) => {
    console.error("Redis error:", err);
});

redisPub.on("reconnecting", () => {
    console.log("Redis reconnecting...");
});

redisSub.on("error", (err) => {
    console.error("Redis error:", err);
});

redisSub.on("reconnecting", () => {
    console.log("Redis reconnecting...");
});


// default ttl for order
const orderStatusTTL = 2 * 60 * 60 // 2 hours 


// sockets mapping
const sockets = new Map();

function verifyJWT(token) {
    if (!JWT_PUBLIC_KEY) {
        console.error("JWT public key not available");
        return null;
    }
    try {
        return jwt.verify(token, JWT_PUBLIC_KEY, { "algorithms": "RS256" })
    } catch (error) {
        console.error("JWT verification error:", error.message)
        return null
    }
}

// helper methods for subscribe and unsubscribe

function subscribeToRoom(ws, room) {
    ws.subscribe(room);
}


// uwebsocket server app
const app = uWS.App()


// Health check endpoint
app.get('/health', (res, req) => {
    res.writeStatus('200 OK').writeHeader('Content-Type', 'application/json').end(JSON.stringify({
        status: 'healthy',
        service: 'uwsocket',
        port: PORT
    }));
});

// websokcet endpoint --- others joins the socket server app using this
app.ws("/*", {
    idleTimeout: 60, // seconds
    maxBackpressure: 1024 * 1024,
    maxPayloadLength: 64 * 1024,
    // this is called before and http connectio is upgraded to tcp socket, we do authentication
    upgrade: (res, req, context) => {
        try {
            const token = req.getQuery('token');
            const claims = verifyJWT(token);

            if (!claims) {
                res.writeStatus('401 Unauthorized').end();
                return;
            }
            res.upgrade(
                { claims },
                req.getHeader('sec-websocket-key'),
                req.getHeader('sec-websocket-protocol'),
                req.getHeader('sec-websocket-extensions'),
                context
            );
        } catch (err) {
            console.error("Upgrade error:", err);
            if (!res.aborted) {
                res.writeStatus('500 Internal Server Error').end();
            }
        }
    },
    open: async (ws, req) => {
        const claims = ws.claims;
        const userId = claims.user_id;
        if (userId) {
            ws.id = `${userId}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
            // Default personal room
            const userRoom = `user:${userId}`;
            subscribeToRoom(ws, userRoom);
            sockets.set(ws.id, ws);
            // saving onlin status to redis for django to replace with  FCM, APNs if offline
            await redisPub.hSet("ws:users", userId, "1");

        }
    },
    // this messages only come from client web sockets, e.g. mobil apps + web browsers
    message: async (ws, message, isBinary) => {
            // setting message type like notification or location and its related data
            let messageData;
            try {
                messageData = JSON.parse(Buffer.from(message).toString());
            } catch (error) {
                console.error("Invalid JSON received:", error.message);
                ws.send(JSON.stringify({ error: "Invalid message format" }));
                return;
            }
            
            const { type, data } = messageData;
            switch (type) {
                case "SUBSCRIBE_ORDER": {
                    const key = `order:${data.orderId}:status`;
                    const exists = await redisPub.exists(key);
                    let room = `order:${data.orderId}`;
                    subscribeToRoom(ws, room); // always subscribe
                    if (exists) {
                        ws.send(JSON.stringify({
                            ok: true,
                            type: "SUBSCRIBED",
                        }));
                        // sending latest status 
                        var latestStatus = await redisPub.get(key);
                        latestStatus = JSON.parse(latestStatus)
                        const type = latestStatus.type
                        const data = latestStatus.data
                        console.log("existed before status type:",type)
                        console.log("data:",data)
                        ws.send(JSON.stringify({
                            type: type,
                            data: data
                        }))
                    }

                    else {
                        ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', data: null }))

                    }
                    break
                }
                case "UNSUBSCRIBE_ORDER": {
                    let room = `order:${data.orderId}`;
                    ws.unsubscribe(room);
                    ws.send(JSON.stringify({ ok: true, type: 'UNSUBSCRIBED', room }))
                    break
                }
                case "SUBSCRIBE_CARRIER": {
                    let room = `carrier:${data.carrierId}`;
                    subscribeToRoom(ws, room);
                    var lastCarrierLocation = await redisPub.get(`carrier_last_${data.carrierId}`)
                    if (!lastCarrierLocation) {
                        lastCarrierLocation = {}
                    } else {
                        lastCarrierLocation = JSON.parse(lastCarrierLocation)
                    }
                    ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED' }))
                    if (lastCarrierLocation.latitude && lastCarrierLocation.longitude) {
                        ws.send(JSON.stringify({ type: "CARRIER_LOCATION", data: { lat: lastCarrierLocation.latitude, lon: lastCarrierLocation.longitude,  ts: Date.now().toString() } }))
                    }
                    break;
                }
                case "UNSUBSCRIBE_CARRIER": {
                    let room = `carrier:${data.carrierId}`;
                    ws.unsubscribe(room)
                    ws.send(JSON.stringify({ ok: true, type: 'UNSUBSCRIBED', room }))
                    break
                }
                case "SUBSCRIBE_VENDOR": {
                    let room = `vendor:${data.vendorId}`;
                    subscribeToRoom(ws, room);
                    ws.send(JSON.stringify({ ok: true, type: "SUBSCRIBED", room }))
                    break;
                }

                case "CARRIER_LOCATION": {
                    redisPub.set(`carrier_last_${data.carrierId}`, JSON.stringify({ latitude: data.latitude, longitude: data.longitude }), { EX: 3600 }); // 1 hour ttl
                    redisPub.publish(`pub:carrier:${data.carrierId}`, JSON.stringify({ type: "CARRIER_LOCATION", data: { latitude: data.latitude, longitude: data.longitude } }));
                    break

                }

                case "VENDOR_ACCEPTED": {
                    const orderId = data.orderId;
                    const key = `order:${orderId}:status`;
                    const payload = {
                        type: "VENDOR_ACCEPTED",
                        data: data
                    };

                    const jsonData = JSON.stringify(payload);
                    await redisPub.set(key, jsonData, { EX: orderStatusTTL });
                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "VENDOR_ACCEPTED", data: data })
                    );
                    // -------- unsubscribing vendor from this order-----------
                    setTimeout(()=>{
                        let room = `order:${data.orderId}`;
                        try {
                            ws.unsubscribe(room);
                        } catch (e) {
                            // socket already closed, ignore
                        }
                    },1000)
                    break;
                }

                case "VENDOR_REJECTED": {
                    const orderId = data.orderId;
                    const key = `order:${orderId}:status`;

                    const payload = {
                        type: "VENDOR_REJECTED",
                        data: data
                    };
                    console.log("vendor rejected payload:",payload)
                    const jsonData = JSON.stringify(payload);
                    await redisPub.set(key, jsonData, { EX: orderStatusTTL });
                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "VENDOR_REJECTED", data: data })
                    );
                    // -------- unsubscribing vendor from this order-----------
                    setTimeout(() => {
                        let room = `order:${data.orderId}`;
                        ws.unsubscribe(room);
                    }, 2000)
                    break;
                }
                case "ORDER_CANCELLED": {
                    const orderId = data.orderId;
                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "ORDER_CANCELLED", data: data })
                    );
                    break;
                }

                default:
                    console.error("unknown message type to uWS server", )
                    ws.send(JSON.stringify({ ok: false, error: "UNKNOWN_TYPE" }));
                }

         
    },

    close: (ws) => {
        const { sub: userId } = ws.claims;
        if (userId) {
            redisPub.hDel("ws:users", userId)
        }
        // unSubscribeAll(ws)
    }
});
// this is where messages come from django or any server connected to redis and call redis.publish
// sending messages comming from redis publisher to all clients connected to its room
redisSub.pSubscribe("pub:*", (message, channel) => {
    const room = channel.replace(/^pub:/, "");
    app.publish(room, message)
});



app.listen(Number(PORT), '0.0.0.0', (token) => {
    console.log('uWS listening on', PORT);
});


