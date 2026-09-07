// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract CampaignVault {
    event CampaignFunded(uint256 indexed campaignId, address indexed merchant, uint256 amount);

    // TODO(day 2)
    function createCampaign(uint256 rewardPerVisit, uint256 dailyCap, bytes32 geohash, uint256 radius) external returns (uint256 campaignId) {
        revert("not implemented");
    }

    function fund(uint256 campaignId, uint256 amount) external {
        revert("not implemented");
    }

    function withdraw(uint256 campaignId) external {
        revert("not implemented");
    }
}