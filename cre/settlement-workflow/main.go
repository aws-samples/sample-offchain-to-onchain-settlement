//go:build wasip1

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/big"
	"strings"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/crypto"
	protos "github.com/smartcontractkit/chainlink-protos/cre/go/sdk"
	"github.com/smartcontractkit/cre-sdk-go/capabilities/blockchain/evm"
	"github.com/smartcontractkit/cre-sdk-go/capabilities/networking/http"
	"github.com/smartcontractkit/cre-sdk-go/capabilities/scheduler/cron"
	"github.com/smartcontractkit/cre-sdk-go/cre"
	"github.com/smartcontractkit/cre-sdk-go/cre/wasm"
)

const (
	intentMintOnly    = "MINT_ONLY"
	intentBurnAndMint = "BURN_AND_MINT"
	intentBurnOnly    = "BURN_ONLY"
)

// Config is loaded from config.staging.json / config.production.json.
type Config struct {
	Schedule        string `json:"schedule"`
	AwsApiBase      string `json:"awsApiBase"`
	ReceiverAddress string `json:"receiverAddress"`
	ChainSelector   uint64 `json:"chainSelector"`
	ChainId         uint64 `json:"chainId"`
	GasLimit        uint64 `json:"gasLimit"`
	WorkflowRunId   string `json:"workflowRunId"`
}

// PendingResponse matches GET /instructions/pending.
type PendingResponse struct {
	Pending []PendingItem `json:"pending"`
}

type PendingItem struct {
	Instruction Instruction `json:"instruction"`
	Signature   string      `json:"signature"`
}

type Instruction struct {
	InstructionId string `json:"instructionId"`
	MessageDigest string `json:"messageDigest"`
	Asset         string `json:"asset"`
	Amount        string `json:"amount"`
	FromParty     string `json:"fromParty"`
	ToParty       string `json:"toParty"`
	ValueTime     uint64 `json:"valueTime"`
	CreatedAt     uint64 `json:"createdAt"`
	Expiry        uint64 `json:"expiry"`
	Intent        string `json:"intent"`
	ChainId       uint64 `json:"chainId"`
	Nonce         string `json:"nonce"`
}

type StatusConfig struct {
	AwsApiBase    string
	InstructionId string
	Status        string
	TxHash        string
	WorkflowRunId string
	ChainId       uint64
	Reason        string
}

type StatusPayload struct {
	Status        string `json:"status"`
	TxHash        string `json:"txHash"`
	WorkflowRunId string `json:"workflowRunId"`
	ChainId       uint64 `json:"chainId"`
	Reason        string `json:"reason"`
}

type StatusResponse struct {
	StatusCode uint32 `json:"statusCode" consensus_aggregation:"identical"`
}

type CanonicalSettlementInstruction struct {
	InstructionId [32]byte
	MessageDigest [32]byte
	Asset         common.Address
	Amount        *big.Int
	FromParty     common.Address
	ToParty       common.Address
	ValueTime     uint64
	CreatedAt     uint64
	Expiry        uint64
	Intent        uint8
	ChainId       *big.Int
	Nonce         [32]byte
}

type SettlementReport struct {
	Instruction CanonicalSettlementInstruction
	Signature   []byte
}

type Result struct {
	Processed int `json:"processed"`
	Succeeded int `json:"succeeded"`
	Failed    int `json:"failed"`
}

func InitWorkflow(config *Config, logger *slog.Logger, secretsProvider cre.SecretsProvider) (cre.Workflow[*Config], error) {
	return cre.Workflow[*Config]{
		cre.Handler(
			cron.Trigger(&cron.Config{Schedule: config.Schedule}),
			onCronTrigger,
		),
	}, nil
}

func fetchPending(config *Config, logger *slog.Logger, sendRequester *http.SendRequester, apiKey string) (*PendingResponse, error) {
	req := &http.Request{
		Url:    strings.TrimRight(config.AwsApiBase, "/") + "/instructions/pending",
		Method: "GET",
		Headers: map[string]string{
			"X-API-Key": apiKey,
		},
	}
	resp, err := sendRequester.SendRequest(req).Await()
	if err != nil {
		return nil, fmt.Errorf("pending request failed: %w", err)
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("pending request status %d", resp.StatusCode)
	}
	var pending PendingResponse
	if err := json.Unmarshal(resp.Body, &pending); err != nil {
		return nil, fmt.Errorf("pending decode failed: %w", err)
	}
	return &pending, nil
}

func postStatus(config *StatusConfig, logger *slog.Logger, sendRequester *http.SendRequester, apiKey string) (*StatusResponse, error) {
	body, err := json.Marshal(StatusPayload{
		Status:        config.Status,
		TxHash:        config.TxHash,
		WorkflowRunId: config.WorkflowRunId,
		ChainId:       config.ChainId,
		Reason:        config.Reason,
	})
	if err != nil {
		return nil, fmt.Errorf("status marshal failed: %w", err)
	}
	req := &http.Request{
		Url:    strings.TrimRight(config.AwsApiBase, "/") + "/instructions/" + config.InstructionId + "/status",
		Method: "POST",
		Body:   body,
		Headers: map[string]string{
			"Content-Type": "application/json",
			"X-API-Key":    apiKey,
		},
	}
	resp, err := sendRequester.SendRequest(req).Await()
	if err != nil {
		return nil, fmt.Errorf("status request failed: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("status request returned non-2xx: %d", resp.StatusCode)
	}
	return &StatusResponse{StatusCode: resp.StatusCode}, nil
}

func onCronTrigger(config *Config, runtime cre.Runtime, trigger *cron.Payload) (*Result, error) {
	logger := runtime.Logger()
	client := &http.Client{}

	logger.Info("CRE Settlement Workflow started",
		"awsApiBase", config.AwsApiBase,
		"receiver", config.ReceiverAddress,
		"chainId", config.ChainId)

	if config.AwsApiBase == "" {
		return nil, fmt.Errorf("awsApiBase is required")
	}
	if !common.IsHexAddress(config.ReceiverAddress) {
		return nil, fmt.Errorf("invalid receiverAddress")
	}
	if config.ChainSelector == 0 {
		return nil, fmt.Errorf("chainSelector is required")
	}

	// Get API key from secrets
	secretReq := &protos.SecretRequest{
		Id: "AWS_API_KEY",
	}
	secret, err := runtime.GetSecret(secretReq).Await()
	if err != nil {
		return nil, fmt.Errorf("failed to get AWS_API_KEY secret: %w", err)
	}
	apiKey := secret.Value
	if apiKey == "" {
		return nil, fmt.Errorf("AWS_API_KEY secret is empty")
	}

	logger.Info("Fetching pending instructions from AWS...")
	pendingPromise := http.SendRequest(config, runtime, client,
		func(cfg *Config, logger *slog.Logger, sendRequester *http.SendRequester) (*PendingResponse, error) {
			return fetchPending(cfg, logger, sendRequester, apiKey)
		},
		cre.ConsensusIdenticalAggregation[*PendingResponse](),
	)
	pending, err := pendingPromise.Await()
	if err != nil {
		return nil, err
	}

	result := &Result{}
	if pending == nil || len(pending.Pending) == 0 {
		logger.Info("No pending instructions")
		return result, nil
	}

	logger.Info("Found pending instructions", "count", len(pending.Pending))

	evmClient := &evm.Client{ChainSelector: config.ChainSelector}
	receiver := common.HexToAddress(config.ReceiverAddress)
	var gasConfig *evm.GasConfig
	if config.GasLimit > 0 {
		gasConfig = &evm.GasConfig{GasLimit: config.GasLimit}
	}

	for _, item := range pending.Pending {
		result.Processed++
		instruction := item.Instruction

		logger.Info("Processing instruction",
			"instructionId", instruction.InstructionId,
			"intent", instruction.Intent,
			"amount", instruction.Amount,
			"from", instruction.FromParty,
			"to", instruction.ToParty,
			"asset", instruction.Asset)

		if config.ChainId != 0 && instruction.ChainId != config.ChainId {
			logger.Info("Skipping unsupported chain", "chainId", instruction.ChainId)
			if err := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				Reason:        "UNSUPPORTED_CHAIN",
			}); err != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", err)
			}
			result.Failed++
			continue
		}

		csi, err := toCSI(instruction)
		if err != nil {
			logger.Error("Invalid CSI", "error", err)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				Reason:        err.Error(),
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		logger.Info("Encoding settlement report...")
		reportBytes, err := encodeReport(csi, item.Signature)
		if err != nil {
			logger.Error("Encode report failed", "error", err)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				Reason:        err.Error(),
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		logger.Info("Generating DON report...")
		reportPromise := runtime.GenerateReport(&cre.ReportRequest{
			EncodedPayload: reportBytes,
			EncoderName:    "evm",
			SigningAlgo:    "ecdsa",
			HashingAlgo:    "keccak256",
		})
		report, err := reportPromise.Await()
		if err != nil {
			logger.Error("Report generation failed", "error", err)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				Reason:        err.Error(),
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		logger.Info("Submitting to blockchain...",
			"receiver", config.ReceiverAddress,
			"gasLimit", config.GasLimit)

		writePromise := evmClient.WriteReport(runtime, &evm.WriteCreReportRequest{
			Receiver:  receiver.Bytes(),
			Report:    report,
			GasConfig: gasConfig,
		})
		resp, err := writePromise.Await()
		if err != nil {
			logger.Error("Write report failed", "error", err)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				Reason:        err.Error(),
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		txHash := fmt.Sprintf("0x%x", resp.TxHash)
		logger.Info("WriteReport reply",
			"instructionId", instruction.InstructionId,
			"txHash", txHash,
			"txStatus", resp.GetTxStatus().String(),
			"receiverStatusSet", resp.ReceiverContractExecutionStatus != nil,
			"receiverStatus", resp.GetReceiverContractExecutionStatus().String(),
			"errorMessage", strings.TrimSpace(resp.GetErrorMessage()))

		if txFailed, failureReason := writeReportFailed(resp); txFailed {
			logger.Error("Transaction failed",
				"txHash", txHash,
				"status", resp.TxStatus,
				"error", failureReason)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				TxHash:        txHash,
				Reason:        failureReason,
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		// Verify on-chain that the settlement was actually executed.
		// The KeystoneForwarder wraps onReport in try/catch, so the tx
		// always succeeds even when the inner call reverts. We must read
		// the executed(instructionId) mapping to confirm.
		executedOnChain, verifyErr := checkExecuted(runtime, evmClient, receiver, csi.InstructionId, resp.TxHash)
		if verifyErr != nil {
			logger.Error("On-chain verification failed", "instructionId", instruction.InstructionId, "error", verifyErr)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				TxHash:        txHash,
				Reason:        fmt.Sprintf("on-chain verification error: %s", verifyErr),
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}
		if !executedOnChain {
			logger.Error("Settlement reverted on-chain (forwarder caught revert)",
				"txHash", txHash,
				"instructionId", instruction.InstructionId)
			if statusErr := sendStatus(runtime, client, apiKey, &StatusConfig{
				AwsApiBase:    config.AwsApiBase,
				InstructionId: instruction.InstructionId,
				Status:        "FAILED",
				WorkflowRunId: config.WorkflowRunId,
				ChainId:       instruction.ChainId,
				TxHash:        txHash,
				Reason:        "RECEIVER_REVERTED",
			}); statusErr != nil {
				logger.Error("Failed to report FAILED status", "instructionId", instruction.InstructionId, "error", statusErr)
			}
			result.Failed++
			continue
		}

		logger.Info("Settlement executed on-chain",
			"txHash", txHash,
			"instructionId", instruction.InstructionId,
			"intent", instruction.Intent,
			"amount", instruction.Amount)

		if err := sendStatus(runtime, client, apiKey, &StatusConfig{
			AwsApiBase:    config.AwsApiBase,
			InstructionId: instruction.InstructionId,
			Status:        "CONFIRMED",
			WorkflowRunId: config.WorkflowRunId,
			ChainId:       instruction.ChainId,
			TxHash:        txHash,
		}); err != nil {
			logger.Error("Failed to report CONFIRMED status", "instructionId", instruction.InstructionId, "error", err)
			result.Failed++
			continue
		}
		result.Succeeded++
	}

	return result, nil
}

func writeReportFailed(resp *evm.WriteReportReply) (bool, string) {
	if resp == nil {
		return true, "missing write report reply"
	}

	errMsg := strings.TrimSpace(resp.GetErrorMessage())
	txStatus := resp.GetTxStatus()
	receiverStatusSet := resp.ReceiverContractExecutionStatus != nil
	receiverStatus := resp.GetReceiverContractExecutionStatus()

	if txStatus != evm.TxStatus_TX_STATUS_SUCCESS {
		if errMsg == "" {
			errMsg = fmt.Sprintf("tx status %s", txStatus.String())
		}
		return true, errMsg
	}

	if !receiverStatusSet {
		if errMsg == "" {
			errMsg = "receiver contract execution status missing"
		}
		return true, errMsg
	}

	if receiverStatus == evm.ReceiverContractExecutionStatus_RECEIVER_CONTRACT_EXECUTION_STATUS_REVERTED {
		if errMsg == "" {
			errMsg = fmt.Sprintf("receiver execution status %s", receiverStatus.String())
		}
		return true, errMsg
	}

	if errMsg != "" {
		// ErrorMessage is optional, but when present it should be treated as a failed write
		// unless explicitly known to be informational.
		return true, errMsg
	}

	return false, ""
}

func checkExecuted(runtime cre.Runtime, evmClient *evm.Client, receiver common.Address, instructionId [32]byte, txHash []byte) (bool, error) {
	// Check the transaction receipt for a SettlementExecuted event
	// matching our instructionId. This avoids read-after-write timing
	// issues that occur when querying contract state immediately after
	// the tx is mined.
	settlementExecutedTopic := crypto.Keccak256([]byte("SettlementExecuted(bytes32,bytes32,address,address,address,uint256,uint8)"))

	resp, err := evmClient.GetTransactionReceipt(runtime, &evm.GetTransactionReceiptRequest{
		Hash: txHash,
	}).Await()
	if err != nil {
		return false, fmt.Errorf("GetTransactionReceipt failed: %w", err)
	}
	if resp.Receipt == nil {
		return false, fmt.Errorf("receipt is nil")
	}

	receiverBytes := receiver.Bytes()
	// The KeystoneForwarder wraps onReport in try/catch, so the outer tx
	// always succeeds. If the inner call reverts, no events from the
	// SettlementConsumer are emitted (reverts undo events).
	//
	// Strategy: Look for the SettlementExecuted event from the receiver.
	// If topics are populated (deployed DON), match normally.
	// If topics are empty (CRE simulation limitation), fall back to
	// checking if any log from the receiver address exists — it only
	// emits on success.

	foundReceiverLog := false
	for _, log := range resp.Receipt.Logs {
		// Primary check: full topic matching (works in deployed DON)
		if len(log.Topics) >= 2 &&
			bytes.Equal(log.Address, receiverBytes) &&
			bytes.Equal(log.Topics[0], settlementExecutedTopic) &&
			bytes.Equal(log.Topics[1], instructionId[:]) {
			return true, nil
		}
		// Fallback: if topics are empty (simulation), the presence of any
		// log from the receiver contract means _settle() ran to completion
		// and emitted SettlementExecuted. If onReport reverted, no logs
		// from the receiver would exist in the receipt.
		if len(log.Topics) == 0 && bytes.Equal(log.Address, receiverBytes) {
			foundReceiverLog = true
		}
	}
	return foundReceiverLog, nil
}

func sendStatus(runtime cre.Runtime, client *http.Client, apiKey string, cfg *StatusConfig) error {
	statusPromise := http.SendRequest(cfg, runtime, client,
		func(statusCfg *StatusConfig, logger *slog.Logger, sendRequester *http.SendRequester) (*StatusResponse, error) {
			return postStatus(statusCfg, logger, sendRequester, apiKey)
		},
		cre.ConsensusIdenticalAggregation[*StatusResponse](),
	)
	_, err := statusPromise.Await()
	return err
}

func toCSI(instruction Instruction) (CanonicalSettlementInstruction, error) {
	instructionId, err := decodeBytes32(instruction.InstructionId)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	messageDigest, err := decodeBytes32(instruction.MessageDigest)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	asset, err := decodeAddress(instruction.Asset)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	fromParty, err := decodeAddress(instruction.FromParty)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	toParty, err := decodeAddress(instruction.ToParty)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	amount, ok := new(big.Int).SetString(instruction.Amount, 10)
	if !ok {
		return CanonicalSettlementInstruction{}, fmt.Errorf("invalid amount")
	}
	intent, err := parseIntent(instruction.Intent)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}
	chainId := new(big.Int).SetUint64(instruction.ChainId)
	nonce, err := decodeBytes32(instruction.Nonce)
	if err != nil {
		return CanonicalSettlementInstruction{}, err
	}

	return CanonicalSettlementInstruction{
		InstructionId: instructionId,
		MessageDigest: messageDigest,
		Asset:         asset,
		Amount:        amount,
		FromParty:     fromParty,
		ToParty:       toParty,
		ValueTime:     instruction.ValueTime,
		CreatedAt:     instruction.CreatedAt,
		Expiry:        instruction.Expiry,
		Intent:        intent,
		ChainId:       chainId,
		Nonce:         nonce,
	}, nil
}

func parseIntent(intent string) (uint8, error) {
	switch intent {
	case intentMintOnly:
		return 0, nil
	case intentBurnAndMint:
		return 1, nil
	case intentBurnOnly:
		return 2, nil
	default:
		return 0, fmt.Errorf("invalid intent")
	}
}

func decodeAddress(raw string) (common.Address, error) {
	if !common.IsHexAddress(raw) {
		return common.Address{}, fmt.Errorf("invalid address")
	}
	return common.HexToAddress(raw), nil
}

func decodeBytes32(raw string) ([32]byte, error) {
	var out [32]byte
	data, err := hexutil.Decode(raw)
	if err != nil {
		return out, fmt.Errorf("invalid bytes32")
	}
	if len(data) != 32 {
		return out, fmt.Errorf("invalid bytes32 length")
	}
	copy(out[:], data)
	return out, nil
}

func decodeSignature(raw string) ([]byte, error) {
	data, err := hexutil.Decode(raw)
	if err != nil {
		return nil, fmt.Errorf("invalid signature")
	}
	if len(data) != 65 {
		return nil, fmt.Errorf("invalid signature length")
	}
	return data, nil
}

func encodeReport(csi CanonicalSettlementInstruction, signatureHex string) ([]byte, error) {
	signature, err := decodeSignature(signatureHex)
	if err != nil {
		return nil, err
	}

	csiComponents := []abi.ArgumentMarshaling{
		{Name: "instructionId", Type: "bytes32"},
		{Name: "messageDigest", Type: "bytes32"},
		{Name: "asset", Type: "address"},
		{Name: "amount", Type: "uint256"},
		{Name: "fromParty", Type: "address"},
		{Name: "toParty", Type: "address"},
		{Name: "valueTime", Type: "uint64"},
		{Name: "createdAt", Type: "uint64"},
		{Name: "expiry", Type: "uint64"},
		{Name: "intent", Type: "uint8"},
		{Name: "chainId", Type: "uint256"},
		{Name: "nonce", Type: "bytes32"},
	}
	_, err = abi.NewType("tuple", "", csiComponents)
	if err != nil {
		return nil, fmt.Errorf("csi tuple type: %w", err)
	}
	reportType, err := abi.NewType("tuple", "", []abi.ArgumentMarshaling{
		{Name: "instruction", Type: "tuple", Components: csiComponents},
		{Name: "signature", Type: "bytes"},
	})
	if err != nil {
		return nil, fmt.Errorf("report tuple type: %w", err)
	}
	args := abi.Arguments{{Name: "report", Type: reportType}}
	encoded, err := args.Pack(SettlementReport{
		Instruction: csi,
		Signature:   signature,
	})
	if err != nil {
		return nil, fmt.Errorf("report pack: %w", err)
	}
	return encoded, nil
}

func main() {
	wasm.NewRunner(cre.ParseJSON[Config]).Run(InitWorkflow)
}
