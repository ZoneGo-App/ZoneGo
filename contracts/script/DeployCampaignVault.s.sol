// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {CampaignVault} from "../src/CampaignVault.sol";

contract DeployCampaignVault is Script {
    // Base Sepolia USDC, official Circle testnet contract.
    address constant USDC = 0x036CbD53842c5426634e7929541eC2318f3dCF7e;

    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerKey);
        CampaignVault vault = new CampaignVault(USDC);
        vm.stopBroadcast();

        console.log("CampaignVault deployed at:", address(vault));
    }
}