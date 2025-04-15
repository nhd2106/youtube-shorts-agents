"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RequestStatus = void 0;
var RequestStatus;
(function (RequestStatus) {
    RequestStatus["PENDING"] = "pending";
    RequestStatus["GENERATING_CONTENT"] = "generating_content";
    RequestStatus["GENERATING_AUDIO"] = "generating_audio";
    RequestStatus["GENERATING_IMAGES"] = "generating_images";
    RequestStatus["WAITING_FOR_IMAGE_SELECTION"] = "waiting_for_image_selection";
    RequestStatus["GENERATING_VIDEO"] = "generating_video";
    RequestStatus["COMPLETED"] = "completed";
    RequestStatus["FAILED"] = "failed";
})(RequestStatus || (exports.RequestStatus = RequestStatus = {}));
//# sourceMappingURL=index.js.map