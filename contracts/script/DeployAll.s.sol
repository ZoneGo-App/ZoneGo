// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {CampaignVault} from "../src/CampaignVault.sol";
import {VisitRegistry} from "../src/VisitRegistry.sol";
import {FraudOracle} from "../src/FraudOracle.sol";

contract DeployAll is Script {
    address constant USDC = 0x036CbD53842c5426634e7929541eC2318f3dCF7e;

    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address worldAttester = vm.envAddress("WORLD_ATTESTER_ADDRESS");
        address fraudOperator = vm.envAddress("FRAUD_OPERATOR_ADDRESS");

        require(worldAttester != address(0), "WORLD_ATTESTER_ADDRESS not set");
        require(fraudOperator != address(0), "FRAUD_OPERATOR_ADDRESS not set");

        vm.startBroadcast(deployerKey);

        CampaignVault vault = new CampaignVault(USDC);
        VisitRegistry registry = new VisitRegistry(address(vault), worldAttester);
        vault.setVisitRegistry(address(registry));
        FraudOracle oracle = new FraudOracle(fraudOperator);

        vm.stopBroadcast();

        console.log("CampaignVault deployed at:", address(vault));
        console.log("VisitRegistry deployed at:", address(registry));
        console.log("FraudOracle deployed at:", address(oracle));
    }
}