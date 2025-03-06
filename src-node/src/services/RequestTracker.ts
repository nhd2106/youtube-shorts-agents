import { v4 as uuidv4 } from "uuid";
import { RequestData, RequestStatus } from "../types";

export class RequestTracker {
  private requests: Map<string, RequestData>;

  constructor() {
    this.requests = new Map();
  }

  createRequest(): string {
    const requestId = uuidv4();
    this.requests.set(requestId, {
      requestId,
      status: RequestStatus.PENDING,
      progress: 0,
      result: null,
      error: null,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    return requestId;
  }

  updateRequest(
    requestId: string,
    updates: {
      status?: RequestStatus;
      progress?: number;
      result?: Record<string, any>;
      error?: string;
    }
  ): void {
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
      updatedRequest.status = RequestStatus.FAILED;
    }

    this.requests.set(requestId, updatedRequest);
  }

  getRequest(requestId: string): RequestData | null {
    const request = this.requests.get(requestId);
    return request || null;
  }

  deleteRequest(requestId: string): void {
    this.requests.delete(requestId);
  }

  cleanOldRequests(maxAgeHours: number = 24): void {
    const maxAge = maxAgeHours * 3600 * 1000; // Convert to milliseconds
    const currentTime = Date.now();

    for (const [requestId, request] of this.requests.entries()) {
      if (currentTime - request.createdAt > maxAge) {
        this.requests.delete(requestId);
      }
    }
  }
}
