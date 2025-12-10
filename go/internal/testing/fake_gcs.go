// Package testing provides internal test utilities for orgdatacore.
package testing

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"sync"
	"time"
)

// FakeBlob represents a fake GCS blob for testing.
type FakeBlob struct {
	Name       string
	Content    []byte
	Generation int64
	Updated    time.Time
}

// FakeBucket represents a fake GCS bucket for testing.
type FakeBucket struct {
	Name  string
	blobs map[string]*FakeBlob
	mu    sync.RWMutex
}

// NewFakeBucket creates a new fake bucket.
func NewFakeBucket(name string) *FakeBucket {
	return &FakeBucket{
		Name:  name,
		blobs: make(map[string]*FakeBlob),
	}
}

// AddBlob adds a blob with content to the bucket.
func (b *FakeBucket) AddBlob(name string, content []byte) *FakeBlob {
	b.mu.Lock()
	defer b.mu.Unlock()

	blob := &FakeBlob{
		Name:       name,
		Content:    content,
		Generation: 1,
		Updated:    time.Now(),
	}
	b.blobs[name] = blob
	return blob
}

// GetBlob retrieves a blob from the bucket.
func (b *FakeBucket) GetBlob(name string) (*FakeBlob, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	blob, ok := b.blobs[name]
	return blob, ok
}

// UpdateBlob updates the content of an existing blob.
func (b *FakeBucket) UpdateBlob(name string, content []byte) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	blob, ok := b.blobs[name]
	if !ok {
		return fmt.Errorf("blob %s not found", name)
	}
	blob.Content = content
	blob.Generation++
	blob.Updated = time.Now()
	return nil
}

// FakeGCSClient represents a fake GCS client for testing.
type FakeGCSClient struct {
	buckets map[string]*FakeBucket
	mu      sync.RWMutex
}

// NewFakeGCSClient creates a new fake GCS client.
func NewFakeGCSClient() *FakeGCSClient {
	return &FakeGCSClient{
		buckets: make(map[string]*FakeBucket),
	}
}

// AddBucket adds a bucket to the client.
func (c *FakeGCSClient) AddBucket(name string) *FakeBucket {
	c.mu.Lock()
	defer c.mu.Unlock()

	bucket := NewFakeBucket(name)
	c.buckets[name] = bucket
	return bucket
}

// GetBucket retrieves a bucket from the client.
func (c *FakeGCSClient) GetBucket(name string) (*FakeBucket, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	bucket, ok := c.buckets[name]
	return bucket, ok
}

// FakeGCSDataSource is a DataSource implementation using fake GCS for testing.
type FakeGCSDataSource struct {
	bucket     *FakeBucket
	objectPath string
	bucketName string
}

// NewFakeGCSDataSource creates a new fake GCS data source.
func NewFakeGCSDataSource(bucketName, objectPath string, content []byte) *FakeGCSDataSource {
	bucket := NewFakeBucket(bucketName)
	bucket.AddBlob(objectPath, content)

	return &FakeGCSDataSource{
		bucket:     bucket,
		objectPath: objectPath,
		bucketName: bucketName,
	}
}

// Load returns a reader for the blob content.
func (f *FakeGCSDataSource) Load(ctx context.Context) (io.ReadCloser, error) {
	blob, ok := f.bucket.GetBlob(f.objectPath)
	if !ok {
		return nil, fmt.Errorf("blob %s not found in bucket %s", f.objectPath, f.bucketName)
	}
	return io.NopCloser(bytes.NewReader(blob.Content)), nil
}

// Watch monitors for changes (simplified for testing - just calls callback once).
func (f *FakeGCSDataSource) Watch(ctx context.Context, callback func() error) error {
	// In a real implementation, this would poll for changes
	// For testing, we just return immediately without starting a watcher
	return nil
}

// String returns a description of this data source.
func (f *FakeGCSDataSource) String() string {
	return fmt.Sprintf("gs://%s/%s (fake)", f.bucketName, f.objectPath)
}

// Close cleans up resources (no-op for fake).
func (f *FakeGCSDataSource) Close() error {
	return nil
}

// UpdateContent updates the blob content for testing hot reload.
func (f *FakeGCSDataSource) UpdateContent(content []byte) error {
	return f.bucket.UpdateBlob(f.objectPath, content)
}

// GetGeneration returns the current generation of the blob.
func (f *FakeGCSDataSource) GetGeneration() (int64, error) {
	blob, ok := f.bucket.GetBlob(f.objectPath)
	if !ok {
		return 0, fmt.Errorf("blob not found")
	}
	return blob.Generation, nil
}
