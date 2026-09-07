// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract CampaignVault {
    using SafeERC20 for IERC20;

    IERC20 public immutable USDC;

    struct Campaign {
        address merchant;
        uint256 rewardPerVisit;
        uint256 dailyCap;
        bytes32 geohash;
        uint256 radius;
        uint256 balance;
    }

    mapping(uint256 => Campaign) public campaigns;
    uint256 public nextCampaignId = 1;

    event CampaignCreated(uint256 indexed campaignId, address indexed merchant, uint256 rewardPerVisit, uint256 dailyCap);
    event CampaignFunded(uint256 indexed campaignId, address indexed merchant, uint256 amount);
    event CampaignWithdrawn(uint256 indexed campaignId, address indexed merchant, uint256 amount);

    constructor(address _usdc) {
        USDC = IERC20(_usdc);
    }

    function createCampaign(uint256 rewardPerVisit, uint256 dailyCap, bytes32 geohash, uint256 radius)
        external
        returns (uint256 campaignId)
    {
        campaignId = nextCampaignId++;
        campaigns[campaignId] = Campaign({
            merchant: msg.sender,
            rewardPerVisit: rewardPerVisit,
            dailyCap: dailyCap,
            geohash: geohash,
            radius: radius,
            balance: 0
        });
        emit CampaignCreated(campaignId, msg.sender, rewardPerVisit, dailyCap);
    }

    function fund(uint256 campaignId, uint256 amount) external {
        Campaign storage c = campaigns[campaignId];
        require(c.merchant != address(0), "campaign does not exist");

        c.balance += amount;
        USDC.safeTransferFrom(msg.sender, address(this), amount);
        emit CampaignFunded(campaignId, msg.sender, amount);
    }

    function withdraw(uint256 campaignId) external {
        Campaign storage c = campaigns[campaignId];
        require(msg.sender == c.merchant, "not merchant");

        uint256 amount = c.balance;
        c.balance = 0;
        USDC.safeTransfer(msg.sender, amount);
        emit CampaignWithdrawn(campaignId, msg.sender, amount);
    }
}