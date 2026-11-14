package stream

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"astrovitals/internal/domain"

	"go.uber.org/zap"
)

type Event struct {
	Name        string
	AstronautID string
	Data        []byte
}

type Client struct {
	ID          string
	AstronautID string // empty means all astronauts
	Channel     chan Event
}

type Hub struct {
	mu      sync.RWMutex
	clients map[string]*Client
	logger  *zap.SugaredLogger
}

func NewHub(logger *zap.SugaredLogger) *Hub {
	return &Hub{
		clients: make(map[string]*Client),
		logger:  logger,
	}
}

func (h *Hub) Subscribe(clientID, astronautID string) *Client {
	h.mu.Lock()
	defer h.mu.Unlock()

	client := &Client{
		ID:          clientID,
		AstronautID: astronautID,
		Channel:     make(chan Event, 64),
	}
	h.clients[clientID] = client
	return client
}

func (h *Hub) Unsubscribe(clientID string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if client, ok := h.clients[clientID]; ok {
		delete(h.clients, clientID)
		close(client.Channel)
	}
}

func (h *Hub) Broadcast(evt Event) {
	h.mu.Lock()
	defer h.mu.Unlock()

	var slowClients []string

	for id, client := range h.clients {
		if client.AstronautID != "" && evt.AstronautID != "" && client.AstronautID != evt.AstronautID {
			continue
		}

		select {
		case client.Channel <- evt:
		default:
			// Buffer full: drop slow client to protect server throughput
			slowClients = append(slowClients, id)
		}
	}

	for _, id := range slowClients {
		if client, ok := h.clients[id]; ok {
			delete(h.clients, id)
			close(client.Channel)
			if h.logger != nil {
				h.logger.Warnw("dropped slow SSE client", "client_id", id)
			}
		}
	}
}

func (h *Hub) BroadcastTelemetry(t domain.Telemetry) {
	// Format as compact JSON per Part 6.5
	payload := map[string]any{
		"astronaut_id": t.AstronautID,
		"recorded_at":  t.RecordedAt.Format(time.RFC3339),
	}
	if t.HeartRate != nil {
		payload["heart_rate"] = *t.HeartRate
	}
	if t.SpO2 != nil {
		payload["spo2"] = *t.SpO2
	}
	if t.Systolic != nil {
		payload["systolic"] = *t.Systolic
	}
	if t.Diastolic != nil {
		payload["diastolic"] = *t.Diastolic
	}
	if t.RespRate != nil {
		payload["resp_rate"] = *t.RespRate
	}
	if t.ECGSummary != nil {
		payload["ecg_summary"] = *t.ECGSummary
	}
	if t.StressIndex != nil {
		payload["stress_index"] = *t.StressIndex
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return
	}

	h.Broadcast(Event{
		Name:        "telemetry",
		AstronautID: t.AstronautID,
		Data:        data,
	})
}

func (h *Hub) BroadcastAlert(a domain.Alert) {
	data, err := json.Marshal(a)
	if err != nil {
		return
	}

	h.Broadcast(Event{
		Name:        "alert",
		AstronautID: a.AstronautID,
		Data:        data,
	})
}

func (h *Hub) BroadcastAlertUpdate(id, status string, updatedAt time.Time, astronautID string) {
	payload := map[string]string{
		"id":         id,
		"status":     status,
		"updated_at": updatedAt.Format(time.RFC3339),
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return
	}

	h.Broadcast(Event{
		Name:        "alert_update",
		AstronautID: astronautID,
		Data:        data,
	})
}

func (h *Hub) ClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

func FormatSSE(event string, data []byte) []byte {
	return []byte(fmt.Sprintf("event: %s\ndata: %s\n\n", event, string(data)))
}
