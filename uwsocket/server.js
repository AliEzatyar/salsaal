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
redisPub.connect();
redisSub.connect();



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

function unSubscribeAll(ws) {
    for (const room of ws.rooms || []) ws.unsubscribe(room);
}

// uwebsocket server app
const app = uWS.App()



// websokcet endpoint --- others joins the socket server app using this
app.ws("/*", {
    idleTimeout: 60, // seconds
    maxBackpressure: 1024 * 1024,
    maxPayloadLength: 64 * 1024,
    // this is called before and http connectio is upgraded to https, we do authentication
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
        const { sub: userId } = ws.claims;
        if (userId) {
            console.log("user connected to uwsocket server, id is: ", userId)
            ws.id = `${userId}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
            ws.rooms = new Set();
            // Default personal room
            const userRoom = `user:${userId}`;
            subscribeToRoom(ws, userRoom);
            ws.rooms.add(userRoom);
            sockets.set(ws.id, ws);
            // saving onlin status to redis for django to replace with  FCM, APNs if offline
            redisPub.hSet("ws:users", userId, "1")
        }
    },
    // this messages only come from client web sockets, e.g. mobil apps + web browsers
    message: async (ws, message, isBinary) => {
        try {
            // setting message type like notification or location and its related data
            const { type, data } = JSON.parse(Buffer.from(message).toString());
            console.log("message came from client to channel")
            switch (type) {
                case "SUBSCRIBE_ORDER": {
                    console.log("subscribed to order ", data.orderId)
                    let room = `order:${data.orderId}`;
                    subscribeToRoom(ws, room);
                    ws.rooms.add(room)
                    ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', room }))
                    break;
                }
                case "UNSUBSCRIBE_ORDER": {
                    let room = `order:${data.orderId}`;
                    console.log("unsubscribed from order", data.orderId)
                    ws.unsubscribe(room);
                    ws.rooms.delete(room);
                    ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', room }))
                    break
                }
                case "SUBSCRIBE_CARRIER": {
                    console.log("subscribed to carrier ", data.carrierId)
                    let room = `carrier:${data.carrierId}`;
                    subscribeToRoom(ws, room);
                    ws.rooms.add(room)
                    ws.send(JSON.stringify({ ok: true, type: 'SUBSCRIBED', room }))
                    break;
                }
                case "SUBSCRIBE_VENDOR": {
                    console.log("subscription to vendor room")
                    let room = `vendor:${data.vendorId}`;
                    subscribeToRoom(ws, room);
                    ws.rooms.add(room);
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
                    redisPub.publish(`pub:carrier:${carrierId}`, JSON.stringify({ type: "LOC", lat, lon, ts }));
                    break

                }
                default:
                    ws.send(JSON.stringify({ ok: false, error: "UNKNOWN_TYPE" }));
            }

        } catch (error) {
            ws.send(JSON.stringify({ ok: false, error: "BAD_PAYLOAD" }));
        }
    },

    close: (ws) => {
        const { sub: userId } = ws.claims;
        console.log("user left")
        if (userId) {
            console.log("iD: ", userId)
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
    console.log('uWS listening on', PORT, "0000");
});
