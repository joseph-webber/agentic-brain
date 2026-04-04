"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ResponseLayer = exports.DeploymentMode = void 0;
var DeploymentMode;
(function (DeploymentMode) {
    DeploymentMode["AIRLOCKED"] = "airlocked";
    DeploymentMode["CLOUD"] = "cloud";
    DeploymentMode["HYBRID"] = "hybrid";
})(DeploymentMode || (exports.DeploymentMode = DeploymentMode = {}));
var ResponseLayer;
(function (ResponseLayer) {
    ResponseLayer["INSTANT"] = "instant";
    ResponseLayer["FAST"] = "fast";
    ResponseLayer["DEEP"] = "deep";
    ResponseLayer["CONSENSUS"] = "consensus";
})(ResponseLayer || (exports.ResponseLayer = ResponseLayer = {}));
