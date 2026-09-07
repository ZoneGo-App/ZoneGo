// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {CampaignVault} from "../src/CampaignVault.sol";
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
        usdc.transfer(merchant, 100e6);
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

    function test_CreateCampaignSucceeds() public {
        vm.prank(merchant);
        uint256 campaignId = vault.createCampaign(1e6, 10e6, bytes32(0), 1000);

        (address m, uint256 rewardPerVisit, uint256 dailyCap,,, uint256 balance) = vault.campaigns(campaignId);
        assertEq(m, merchant);
        assertEq(rewardPerVisit, 1e6);
        assertEq(dailyCap, 10e6);
        assertEq(balance, 0);
    }

    function test_FundAndWithdrawSucceeds() public {
        vm.startPrank(merchant);
        uint256 campaignId = vault.createCampaign(1e6, 10e6, bytes32(0), 1000);
        usdc.approve(address(vault), 100e6);
        vault.fund(campaignId, 100e6);

        (,,,,, uint256 balanceAfterFund) = vault.campaigns(campaignId);
        assertEq(balanceAfterFund, 100e6);

        uint256 merchantBalanceBefore = usdc.balanceOf(merchant);
        vault.withdraw(campaignId);
        vm.stopPrank();

        (,,,,, uint256 balanceAfterWithdraw) = vault.campaigns(campaignId);
        assertEq(balanceAfterWithdraw, 0);
        assertEq(usdc.balanceOf(merchant), merchantBalanceBefore + 100e6);
    }
}