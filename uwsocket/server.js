import uWS from "uWebSockets.js";
import { createClient } from 'redis';
import jwt from 'jsonwebtoken';
import { configDotenv } from "dotenv";
// loading .env variables into process.env
configDotenv()

const PORT = process.env.SERVER_PORT || 3000;

const djangoServerUrl = process.env.DJANGO_SERVER_URL
const redisUrl = process.env.REDIS_URL
console.log(redisUrl, "thi-----redis-url")
// getting public key for verifying user's jwt tokens
const res = await fetch(djangoServerUrl + "/jwtks/");
const JWT_PUBLIC_KEY = await res.text();
console.log("this is the public key", JWT_PUBLIC_KEY)

// creating and connecting redis publisher and subscriber
const redisPub = createClient({
    url: redisUrl,  // <- connection details
})
const redisSub = createClient({
    url: redisUrl,  // <- connection details
})
await redisPub.connect();
await redisSub.connect();
// default ttl for order
const orderStatusTTL = 2 * 60 * 60 // 2 hours 


// sockets mapping
const sockets = new Map();

function verifyJWT(token) {
    try {
        return jwt.verify(token, JWT_PUBLIC_KEY, { "algorithms": "RS256" })
    } catch (error) {
        console.log(error)
        return null
    }
}


// helper methods for subscribe and unsubscribe

function subscribeToRoom(ws, room) {
    ws.subscribe(room);
}


// uwebsocket server app
const app = uWS.App()



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
                console.log("not okay")
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
        console.log("connection......", claims)
        if (userId) {
            console.log("user connected to uwsocket server, id: ", userId)
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
        try {
            // setting message type like notification or location and its related data
            console.log("message.......", Buffer.from(message).toString())
            const { type, data } = JSON.parse(Buffer.from(message).toString());
            console.log("message came from client to channel", type, data)
            switch (type) {
                case "SUBSCRIBE_ORDER": {
                    console.log("subscribed to order ", data.orderId)
                    const key = `order:${data.orderId}:status`;
                    const exists = await redisPub.exists(key);
                    let room = `order:${data.orderId}`;
                    subscribeToRoom(ws, room); // always subscribe
                    if (exists) {
                        console.log("exists");
                        var latestStatus = await redisPub.get(key);
                        latestStatus = JSON.parse(latestStatus)
                        ws.send(JSON.stringify({
                            ok: true,
                            type: "SUBSCRIBED",
                        }));
                        const type = latestStatus.type
                        const data = latestStatus.data
                        ws.send(JSON.stringify({
                            type: type,
                            data: data
                        }))
                    }

                    else {
                        console.log("it did not exist")
                        ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', data: null }))

                    }
                    break
                }
                case "UNSUBSCRIBE_ORDER": {

                    let room = `order:${data.orderId}`;
                    console.log("unsubscribed from order", data.orderId)
                    ws.unsubscribe(room);
                    ws.send(JSON.stringify({ ok: true, type: 'UNSUBSCRIBED', room }))
                    break
                }
                case "SUBSCRIBE_CARRIER": {
                    console.log("subscribed to carrier ", data.carrierId)
                    let room = `carrier:${data.carrierId}`;
                    subscribeToRoom(ws, room);
                    ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', room }))
                    break;
                }
                case "UNSUBSCRIBE_CARRIER": {
                    console.log("leaving carrier room");
                    let room = `carrier:${data.carrierId}`;
                    ws.unsubscribe(room)
                    ws.send(JSON.stringify({ ok: true, type: 'UNSUBSCRIBED', room }))
                    break
                }
                case "SUBSCRIBE_VENDOR": {
                    console.log("subscription to vendor room")
                    let room = `vendor:${data.vendorId}`;
                    subscribeToRoom(ws, room);
                    ws.send(JSON.stringify({ ok: true, type: "SUBSCRIBED", room }))
                    break;
                }

                case "CARRIER_LOCATION": {
                    const { lat, lon, carrierId, ts } = data;
                    redisPub.geoAdd("carrier_location", {
                        longitude: lon.toString(),
                        latitude: lat.toString(),
                        member: carrierId.toString()   // must be "member" not "carrierId"
                    });
                    redisPub.hSet(`carrier_last_${carrierId}`, { latitude: lat, longitude: lon, ts });
                    redisPub.publish(`pub:carrier:${carrierId}`, JSON.stringify({ type: "CARRIER_LOCATION", lat, lon, ts }));
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

                    console.log("order status saved in server accepted", jsonData);

                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "VENDOR_ACCEPTED", data: data })
                    );
                    break;
                }

                case "VENDOR_REJECTED": {
                    const orderId = data.orderId;
                    const key = `order:${orderId}:status`;

                    const payload = {
                        status: "VENDOR_REJECTED",
                        data: null
                    };

                    const jsonData = JSON.stringify(payload);
                    await redisPub.set(key, jsonData, { EX: orderStatusTTL });

                    console.log("order status saved in server rejected", jsonData);

                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "VENDOR_REJECTED", data: payload })
                    );
                    break;
                }

                case "BUYER_FINALIZED": {
                    const orderId = data.orderId;
                    const key = `order:${orderId}:status`;

                    const payload = {
                        type: "BUYER_FINALIZED",
                        data
                    };

                    const jsonData = JSON.stringify(payload);
                    await redisPub.set(key, jsonData);

                    console.log("order status saved in server buyer finalized", jsonData);

                    redisPub.publish(
                        `pub:order:${orderId}`,
                        JSON.stringify({ type: "BUYER_FINALIZED", data: data })
                    );
                    break;
                }





                default:
                    ws.send(JSON.stringify({ ok: false, error: "UNKNOWN_TYPE" }));
            }

        } catch (error) {
            console.log(error)
            ws.send(JSON.stringify({ ok: false, error: "BAD_PAYLOAD" }));
        }
    },

    close: (ws) => {
        const { sub: userId } = ws.claims;
        console.log("user left", userId)
        if (userId) {
            redisPub.hDel("ws:users", userId)
        }
        // unSubscribeAll(ws)
    }
});
// this is where messages come from django or any server connected to redis and call redis.publish
// sending messages comming from redis publisher to all clients connected to its room
redisSub.pSubscribe("pub:*", (message, channel) => {
    console.log("message come to redis subsciber")
    const room = channel.replace(/^pub:/, "");
    console.log(room)
    app.publish(room, message)
});



app.listen(Number(PORT), '0.0.0.0', (token) => {
    console.log('uWS listening on', PORT);
});
