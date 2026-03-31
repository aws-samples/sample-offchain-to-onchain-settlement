// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/KeyRegistry.sol";
import "../contracts/SettlementConsumer.sol";
import "../contracts/Token.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address admin = vm.addr(deployerPrivateKey);
        address kmsSigner = vm.envAddress("KMS_SIGNER");
        uint256 chainId = vm.envOr("CHAIN_ID", uint256(11155111));
        uint256 chainSelector = vm.envOr("CHAIN_SELECTOR", uint256(16015286601757825753));
        string memory rpcUrl = vm.envOr("RPC_URL", string("https://ethereum-sepolia-rpc.publicnode.com"));
        string memory awsRegion = vm.envOr("AWS_REGION", string("us-east-1"));
        string memory creChainName = vm.envOr("CRE_CHAIN_NAME", string("ethereum-testnet-sepolia"));
        // For Sepolia testnet local/simulation deployments we default to the CRE simulator MockForwarder,
        // but allow overriding via .env KEYSTONE_FORWARDER for easy reconfiguration.
        address keystoneForwarder = vm.envOr(
            "KEYSTONE_FORWARDER",
            address(0x15fC6ae953E024d975e77382eEeC56A9101f9F88)
        );

        console.log("Deploying with admin address:", admin);
        console.log("KMS Signer:", kmsSigner);
        console.log("Keystone Forwarder:", keystoneForwarder);

        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy KeyRegistry
        KeyRegistry keyRegistry = new KeyRegistry(admin, kmsSigner);
        console.log("KeyRegistry deployed at:", address(keyRegistry));

        // 2. Deploy SettlementConsumer
        SettlementConsumer settlementConsumer = new SettlementConsumer(
            address(keyRegistry),
            keystoneForwarder
        );
        console.log("SettlementConsumer deployed at:", address(settlementConsumer));

        // 3. Deploy Token
        Token token = new Token("TestToken", "TKN", address(settlementConsumer));
        console.log("Token deployed at:", address(token));

        vm.stopBroadcast();

        // Read existing values from .env to preserve them
        string memory privateKey = vm.envString("PRIVATE_KEY");

        // Write addresses to .env file
        string memory envContent = string.concat(
            "# Deployment Configuration (set before running deployment script)\n",
            "PRIVATE_KEY=", privateKey, "\n",
            "AWS_REGION=", awsRegion, "\n",
            "CHAIN_ID=", vm.toString(chainId), "\n",
            "CHAIN_SELECTOR=", vm.toString(chainSelector), "\n",
            "RPC_URL=", rpcUrl, "\n",
            "CRE_CHAIN_NAME=", creChainName, "\n\n",
            "KEYSTONE_FORWARDER=", vm.toString(keystoneForwarder), "\n\n",
            "# Contract Addresses (auto-populated by script/Deploy.s.sol)\n",
            "KEY_REGISTRY=", vm.toString(address(keyRegistry)), "\n",
            "SETTLEMENT_CONSUMER=", vm.toString(address(settlementConsumer)), "\n",
            "TOKEN=", vm.toString(address(token)), "\n",
            "KMS_SIGNER=", vm.toString(kmsSigner), "\n",
            "YOUR_ADDRESS=", vm.toString(admin), "\n"
        );
        vm.writeFile(".env", envContent);
        console.log("\nAddresses written to .env file");
    }
}
