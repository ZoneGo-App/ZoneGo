// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {CampaignVault} from "../src/CampaignVault.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USDC", "USDC") {
        _mint(msg.sender, 1_000_000e6);
    }
}

contract CampaignVaultTest is Test {
    CampaignVault vault;
    MockUSDC usdc;
    address merchant = address(0x1);
    address stranger = address(0x2);

    function setUp() public {
        usdc = new MockUSDC();
        vault = new CampaignVault(address(usdc));
    }

    function test_FundNonexistentCampaignReverts() public {
        vm.expectRevert("campaign does not exist");
        vault.fund(999, 100);
    }

    function test_WithdrawNotMerchantReverts() public {
        vm.prank(merchant);
        uint256 campaignId = vault.createCampaign(1e6, 10e6, bytes32(0), 1000);

        vm.prank(stranger);
        vm.expectRevert("not merchant");
        vault.withdraw(campaignId);
    }
}