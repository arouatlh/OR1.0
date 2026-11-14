package responses

import (
	"encoding/json"
	"net/http"
	"strconv"
)

type ErrorResponse struct {
	Message    string `json:"message"`
	StatusCode int    `json:"status_code"`
}

func WriteErrorResponseToJSON(w http.ResponseWriter, statusCode int, err error) {
	response := ErrorResponse{
		Message:    err.Error(),
		StatusCode: statusCode,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}

type SuccessResponse struct {
	Message    string `json:"message"`
	Data       any    `json:"data"`
	StatusCode int    `json:"status_code"`
}

func WriteSuccessResponseToJSON(w http.ResponseWriter, statusCode int, data any) {
	response := SuccessResponse{
		Message:    "Success",
		Data:       data,
		StatusCode: statusCode,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}

type Pagination struct {
	Offset int `json:"offset"`
	Limit  int `json:"limit"`
	Total  int `json:"total"`
}

type PaginatedResponse struct {
	Message    string `json:"message"`
	Data       any    `json:"data"`
	StatusCode int    `json:"status_code"`
	Count      int    `json:"count"`
}

// WritePaginatedResponseToJSON writes paginated response to writer. Count = number of items in this page.
func WritePaginatedResponseToJSON(w http.ResponseWriter, statusCode int, data any, count int) {
	response := PaginatedResponse{
		Message:    "Success",
		Data:       data,
		StatusCode: statusCode,
		Count:      count,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}

// GetPaginationParams returns (offset, limit). Note the ORDER: offset first.
func GetPaginationParams(r *http.Request) (int, int) {
	defaultLimit := 20
	defaultOffset := 0

	limit := defaultLimit
	if l, err := strconv.Atoi(r.URL.Query().Get("limit")); err == nil && l > 0 {
		limit = l
	}

	offset := defaultOffset
	if o, err := strconv.Atoi(r.URL.Query().Get("offset")); err == nil && o > 0 {
		offset = o
	}

	return offset, limit
}
