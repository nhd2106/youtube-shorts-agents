"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RequestTracker = void 0;
const uuid_1 = require("uuid");
const types_1 = require("../types");
class RequestTracker {
    constructor() {
        this.requests = new Map();
    }
    createRequest() {
        const requestId = (0, uuid_1.v4)();
        this.requests.set(requestId, {
            requestId,
            status: types_1.RequestStatus.PENDING,
            progress: 0,
            result: null,
            error: null,
            createdAt: Date.now(),
            updatedAt: Date.now(),
        });
        return requestId;
    }
    updateRequest(requestId, updates) {
        const request = this.requests.get(requestId);
        if (!request) {
            throw new Error(`Request ${requestId} not found`);
        }
        const updatedRequest = {
            ...request,
            ...updates,
            updatedAt: Date.now(),
        };
        if (updates.error) {
            updatedRequest.status = types_1.RequestStatus.FAILED;
        }
        this.requests.set(requestId, updatedRequest);
    }
    getRequest(requestId) {
        const request = this.requests.get(requestId);
        return request || null;
    }
    deleteRequest(requestId) {
        this.requests.delete(requestId);
    }
    cleanOldRequests(maxAgeHours = 24) {
        const maxAge = maxAgeHours * 3600 * 1000;
        const currentTime = Date.now();
        for (const [requestId, request] of this.requests.entries()) {
            if (currentTime - request.createdAt > maxAge) {
                this.requests.delete(requestId);
            }
        }
    }
}
exports.RequestTracker = RequestTracker;
//# sourceMappingURL=RequestTracker.js.map