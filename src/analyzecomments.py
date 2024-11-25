import numpy as np
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d


class AnalyzeComments:

    def __init__(self, comments, video_length, time_bin=30):
        self.comments = comments
        self.video_length = video_length
        self.time_bin = time_bin

    def _aggregate_comments(self):
        bins = np.arange(0, self.video_length + self.time_bin, self.time_bin)
        counts = np.zeros(len(bins) - 1, dtype=int)

        for comment in self.comments:
            time = comment["content_offset_seconds"]
            index = np.digitize(time, bins) - 1
            if 0 <= index < len(counts):
                counts[index] += 1

        return counts, bins

    def _calculate_diversity_score(self):
        bins = np.arange(0, self.video_length + self.time_bin, self.time_bin)
        diversity_scores = np.zeros(len(bins) - 1)

        for comment in self.comments:
            time = comment["content_offset_seconds"]
            message = comment["message"]
            index = np.digitize(time, bins) - 1
            if 0 <= index < len(diversity_scores):
                diversity_scores[index] += len(set(message))

        return diversity_scores / (np.max(diversity_scores) + 1e-10)

    def _calculate_burstiness_score(self, counts):
        burstiness = np.diff(counts, prepend=0)
        return np.abs(burstiness) / (np.max(np.abs(burstiness)) + 1e-10)

    def detect_peaks(self, sensitivity=5):
        counts, bins = self._aggregate_comments()
        diversity_scores = self._calculate_diversity_score()
        burstiness_scores = self._calculate_burstiness_score(counts)

        combined_scores = counts / (np.max(counts) + 1e-10)
        combined_scores += diversity_scores * 0.5
        combined_scores += burstiness_scores * 0.5

        smoothed_scores = gaussian_filter1d(combined_scores, sigma=2)

        height_threshold = np.percentile(smoothed_scores, 90 - sensitivity * 7)
        distance_threshold = max(2, int(10 / sensitivity))

        peaks, _ = find_peaks(smoothed_scores,
                              height=height_threshold,
                              distance=distance_threshold)

        return bins[:-1], smoothed_scores, peaks
