// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {SettlementConsumer} from "contracts/SettlementConsumer.sol";
import {KeyRegistry} from "contracts/KeyRegistry.sol";
import {Token} from "contracts/Token.sol";

interface Vm {
    function addr(uint256 privateKey) external returns (address);
    function sign(uint256 privateKey, bytes32 digest) external returns (uint8 v, bytes32 r, bytes32 s);
    function warp(uint256 newTimestamp) external;
    function expectRevert(bytes calldata) external;
    function prank(address msgSender) external;
}

contract SettlementConsumerTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    KeyRegistry private registry;
    SettlementConsumer private consumer;
    Token private token;

    uint256 private signerPk;
    address private signer;
    address private forwarder;

    function setUp() public {
        signerPk = 0xA11CE;
        signer = vm.addr(signerPk);
        forwarder = address(0xBEEF);

        registry = new KeyRegistry(address(this), signer);
        consumer = new SettlementConsumer(address(registry), forwarder);
        token = new Token("Test", "TST", address(consumer));

        vm.warp(1_700_000_000);
    }

    function test_forwarder_only() public {
        SettlementConsumer.CanonicalSettlementInstruction memory csi = _buildCsi(uint64(block.timestamp + 100));
        bytes memory report = _buildReport(csi, signerPk);

        vm.expectRevert(bytes("FORWARDER_ONLY"));
        consumer.onReport("", report);
    }

    function test_replay_reverts() public {
        SettlementConsumer.CanonicalSettlementInstruction memory csi = _buildCsi(uint64(block.timestamp + 100));
        bytes memory report = _buildReport(csi, signerPk);

        _callAsForwarder(report);

        vm.expectRevert(bytes("ALREADY_EXECUTED"));
        _callAsForwarder(report);
    }

    function test_bad_signer_reverts() public {
        uint256 badPk = 0xBAD123;
        SettlementConsumer.CanonicalSettlementInstruction memory csi = _buildCsi(uint64(block.timestamp + 100));
        bytes memory report = _buildReport(csi, badPk);

        vm.expectRevert(bytes("SIGNER_UNAUTHORIZED"));
        _callAsForwarder(report);
    }

    function test_expired_reverts() public {
        SettlementConsumer.CanonicalSettlementInstruction memory csi = _buildCsi(uint64(block.timestamp - 1));
        bytes memory report = _buildReport(csi, signerPk);

        vm.expectRevert(bytes("EXPIRED"));
        _callAsForwarder(report);
    }

    function test_end_to_end_happy_path_smoke() public {
        SettlementConsumer.CanonicalSettlementInstruction memory csi = _buildCsi(uint64(block.timestamp + 300));
        bytes memory report = _buildReport(csi, signerPk);

        _callAsForwarder(report);

        require(consumer.executed(csi.instructionId), "instruction not executed");
        require(token.balanceOf(csi.toParty) == csi.amount, "recipient not minted");
        require(token.totalSupply() == csi.amount, "supply mismatch");
    }

    function _callAsForwarder(bytes memory report) internal {
        vm.prank(forwarder);
        consumer.onReport("", report);
    }

    function _buildReport(
        SettlementConsumer.CanonicalSettlementInstruction memory csi,
        uint256 pk
    ) internal returns (bytes memory) {
        bytes32 digest = _hashTypedData(csi);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        SettlementConsumer.SettlementReport memory report = SettlementConsumer.SettlementReport({
            instruction: csi,
            signature: signature
        });

        return abi.encode(report);
    }

    function _buildCsi(uint64 expiry) internal view returns (SettlementConsumer.CanonicalSettlementInstruction memory csi) {
        csi.messageDigest = keccak256("raw-message");
        csi.asset = address(token);
        csi.amount = 1 ether;
        csi.fromParty = address(0);
        csi.toParty = address(0xCAFE);
        csi.valueTime = uint64(block.timestamp);
        csi.createdAt = uint64(block.timestamp - 10);
        csi.expiry = expiry;
        csi.intent = 0;
        csi.chainId = block.chainid;
        csi.nonce = keccak256("nonce-1");
        csi.instructionId = _deriveInstructionId(csi);
    }

    function _deriveInstructionId(
        SettlementConsumer.CanonicalSettlementInstruction memory csi
    ) internal pure returns (bytes32) {
        return keccak256(
            abi.encodePacked(
                "CSI_V1",
                csi.messageDigest,
                csi.asset,
                csi.amount,
                csi.fromParty,
                csi.toParty,
                csi.valueTime,
                csi.intent,
                csi.chainId,
                csi.createdAt,
                csi.expiry,
                csi.nonce
            )
        );
    }

    function _hashTypedData(
        SettlementConsumer.CanonicalSettlementInstruction memory csi
    ) internal view returns (bytes32) {
        bytes32 domainTypeHash = keccak256(
            "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        );
        bytes32 csiTypeHash = keccak256(
            "CanonicalSettlementInstruction(bytes32 instructionId,bytes32 messageDigest,address asset,uint256 amount,address fromParty,address toParty,uint64 valueTime,uint64 createdAt,uint64 expiry,uint8 intent,uint256 chainId,bytes32 nonce)"
        );

        bytes32 domain = keccak256(
            abi.encode(
                domainTypeHash,
                keccak256(bytes("SettlementInstruction")),
                keccak256(bytes("1")),
                block.chainid,
                address(consumer)
            )
        );

        bytes32 structHash = keccak256(
            abi.encode(
                csiTypeHash,
                csi.instructionId,
                csi.messageDigest,
                csi.asset,
                csi.amount,
                csi.fromParty,
                csi.toParty,
                csi.valueTime,
                csi.createdAt,
                csi.expiry,
                csi.intent,
                csi.chainId,
                csi.nonce
            )
        );

        return keccak256(abi.encodePacked("\x19\x01", domain, structHash));
    }
}
